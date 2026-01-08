# CLAUDE_DETAILED_STATE.md

Blender particle position control via Python. Successfully implemented frame handler approach to set particle positions and sizes from CSV coordinates. Key insight: don't try to persist positions to file - override them every frame like Molecular Plus does.

**Last updated**: 2026-01-08

---

## SACROSANCT HUMAN OVERARCHING AIMS AND TASK DESCRIPTION (Exact Quotes Only - No Paraphrasing)

> "please carefully reach through all the code and has inside this repository. Then, have a look at the molecular plus plug-in..."
>
> "we can't use vertices. How does molecular plus get around this?"
>
> "I just want to do whatever they do to set particle positions. We know it's possible and we have the source code that does this."
>
> "I don't care at all where they're initialised. This can be completely arbitrary. As long as we have control of it from subsequent frames."
>
> "I would just like you to compile and run your own copy of molecular plus. Eventually, I want to be able to modify this so that we can perform kinds of physics that it wasn't designed to do."

---

## CURRENT GOALS

### Goal 1: Particle Position Control from CSV ✅ COMPLETE
Programmatically set Blender particle positions from CSV without using mesh vertices.

**Status**: SOLVED. Frame handler approach works in both GUI and headless modes.

### Goal 2: Compile and Run Molecular Plus (IN PROGRESS)
Compile the Molecular Plus Cython (.pyx) files to enable custom physics modifications.

**Why**: User wants to modify Molecular Plus to perform physics simulations it wasn't designed for. First step is ensuring we can compile the Cython code autonomously.

**Status**: Starting exploration.

---

## COMPLETED: PARTICLE POSITION CONTROL

### The Problem
Set Blender particle positions programmatically from CSV coordinates without vertex-based emission.

### What Went Wrong (Failed Approaches)

1. **Direct `ps.particles` access**: Always empty (length 0) when running via `--python`
2. **`foreach_set`**: Can't use on empty collection
3. **Writing to evaluated particles**: Changes don't persist to .blend file
4. **Cache baking**: `bpy.ops.ptcache.bake()` fails with context errors
5. **Different particle types**: Same `ps.particles = 0` issue

### The Crucial Insight

**Realization**: We were trying to make positions PERSIST to the .blend file. But that's not how Molecular Plus works!

**How Molecular Plus works**:
- They modify particle properties DURING simulation via modal operators
- They override values on EVERY FRAME, not once at startup
- Position persistence to file is irrelevant - they control positions in real-time

**The solution**: Use a frame change handler to set positions on every frame.

### Working Solution

**Architecture**:
```
frame_change_post handler
    ↓
For each frame change:
    1. Get evaluated depsgraph
    2. Get evaluated particle system (ps_eval.particles IS populated)
    3. Set ps_eval.particles[i].location = CSV coordinate
    4. Set ps_eval.particles[i].velocity = (0,0,0)
    5. Set ps_eval.particles[i].size = base_size * CSV multiplier
    ↓
Particles appear at correct positions/sizes on every frame
```

**Key Code** (`gui_script.py`):
```python
def set_particle_positions(scene, depsgraph):
    """Frame change handler - sets particle positions and sizes every frame"""
    for obj in scene.objects:
        if not obj.particle_systems:
            continue
        obj_eval = obj.evaluated_get(depsgraph)
        for ps_idx, ps_eval in enumerate(obj_eval.particle_systems):
            ps_original = obj.particle_systems[ps_idx]
            base_size = ps_original.settings.particle_size  # From GUI

            for i in range(min(len(_particle_data), len(ps_eval.particles))):
                x, y, z, scale_mult = _particle_data[i]
                ps_eval.particles[i].location = (x, y, z)
                ps_eval.particles[i].velocity = (0, 0, 0)
                ps_eval.particles[i].size = base_size * scale_mult

def register_handler():
    bpy.app.handlers.frame_change_post.append(set_particle_positions)
```

### Why This Works
1. `frame_change_post` fires AFTER Blender evaluates the frame
2. At this point, `ps_eval.particles` IS populated
3. Writing to `ps_eval.particles[i].location` and `.size` updates display
4. Runs on every frame change → positions always correct
5. **Works in headless mode** (`blender --background --python script.py --render-anim`)
6. Works in GUI mode
7. No need for positions to persist to file

### Headless Rendering
```bash
blender --background scene.blend --python gui_script.py --render-anim
```
Each rendered frame triggers `frame_change_post`, handler fires, positions/sizes set, frame renders correctly.

---

## FILE STRUCTURE

```
publication_galaxy_claude/
├── gui_script.py              # Working solution - frame handler approach
├── particles.csv              # 200-point helix with x,y,z,scale columns
├── minimal_poc_result.blend   # Test blend file (200 particles, icosphere instances)
├── CLAUDE_DETAILED_STATE.md   # This file
└── archive_attempts/          # Failed experimental scripts (preserved for reference)
```

### particles.csv Format
```csv
x,y,z,scale
30.0,0.0,-50.0,1.0
29.63,4.69,-49.5,1.095
28.53,9.27,-49.0,1.191
...
```
- 200 rows forming a helix (radius 30, z from -50 to +49.5, 4 full rotations)
- `scale` column: multiplier from 1.0 to 20.0 (applied to GUI base_size)

---

## GOTCHAS AND LESSONS LEARNED

1. **Don't conflate "writable" with "persistent"**: Writing to `ps_eval.particles` works, but doesn't persist to file. Use frame handler to reapply every frame.

2. **Molecular Plus doesn't do magic**: They use standard Blender APIs. The "magic" is their modal operator that runs every frame.

3. **Frame handlers are the answer for real-time control**: Not trying to bake static positions.

4. **`--python` context differs from scripting tab**: Many operations that work in the scripting tab fail via `--python`.

5. **The evaluated depsgraph is your friend**: Even when `ps.particles` is empty, `ps_eval.particles` from the depsgraph is populated.

6. **Halo render ignores individual particle size**: `particle.size` IS writable and the value IS set, but Halo rendering uses fixed size. Use **Object instances** (e.g., icosphere) to see size differences.

7. **CSV count vs particle system count mismatch**: Script uses `min(len(coords), len(particles))`. Always ensure particle system count matches your data.

---

## MOLECULAR PLUS COMPILATION (Goal 2)

### Objective
Compile the Molecular Plus Cython (.pyx) files from source, enabling autonomous modification for custom physics.

### Background
Molecular Plus is a Blender addon that performs molecular dynamics simulations. It uses Cython for performance-critical particle calculations. By compiling it ourselves, we can:
1. Understand the build process
2. Modify the physics calculations
3. Run custom simulations autonomously

### Status
- [ ] Locate Molecular Plus source code
- [ ] Identify .pyx Cython files
- [ ] Understand compilation requirements (Cython, C compiler, Blender Python headers)
- [ ] Compile successfully
- [ ] Verify addon loads in Blender
- [ ] Test basic simulation works

### Notes
(To be filled in as work progresses)

---

## VERIFICATION HISTORY

### 2026-01-07: Initial Solution
- Particles positioned correctly from CSV
- Verified in both headless and GUI modes

### 2026-01-08: Size Control Added
- Added `scale` column to CSV (multiplier 1.0 to 20.0)
- `particle.size = base_size * multiplier` works
- Confirmed: Halo render ignores size (use object instances)
- Created 200-point helix test pattern
- Fixed position formula to maintain original coordinates when adding scale
