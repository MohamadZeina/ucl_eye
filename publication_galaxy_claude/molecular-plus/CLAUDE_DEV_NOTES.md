# Molecular Plus Development Notes

## Quick Reference: File Update Workflow

### Python Files Only (UI changes, parameter changes)
```bash
# Edit in repo, then copy to addon folder - NO reinstall needed
cp /Users/mo/github/ucl_eye/publication_galaxy_claude/molecular-plus/*.py \
   "/Users/mo/Library/Application Support/Blender/4.5/scripts/addons/molecular_plus/"

# Restart Blender - new code loads automatically
```

### Cython Files (core simulation logic)
```bash
cd /Users/mo/github/ucl_eye/publication_galaxy_claude/molecular-plus/c_sources

# Compile
/opt/homebrew/bin/python3.11 setup_arm64.py build_ext --inplace

# Copy compiled module to Blender's Python
cp -r molecular_core/ "/Applications/Blender 4.5.app/Contents/Resources/4.5/python/lib/python3.11/site-packages/"

# Restart Blender
```

---

## Why No Reinstall is Needed

Blender addons work by loading Python files from:
```
~/Library/Application Support/Blender/4.5/scripts/addons/<addon_name>/
```

**Key insight**: Blender doesn't validate or checksum addon files after installation. It simply loads whatever is in that folder when:
1. Blender starts
2. You toggle the addon off/on in preferences
3. You call `bpy.ops.preferences.addon_refresh()`

So the workflow is:
1. Edit files in the git repo
2. Copy directly to the addon folder
3. Restart Blender (or toggle addon)
4. New code loads automatically

This saves the tedious cycle of: Preferences → Add-ons → Uninstall → Install from file → Enable.

---

## The Parameter Pipeline

Data flows from Blender UI to Cython core through 6 files:

```
┌─────────────────┐
│  properties.py  │  Define Blender property (slider/checkbox)
│                 │  parset.mol_gravity_rotation_falloff = FloatProperty(...)
└────────┬────────┘
         │
┌────────▼────────┐
│     ui.py       │  Display in panel
│                 │  row.prop(psys.settings, "mol_gravity_rotation_falloff")
└────────┬────────┘
         │
┌────────▼────────┐
│   simulate.py   │  Pack into params array at specific index
│                 │  params[55] = psys_settings.mol_gravity_rotation_falloff
└────────┬────────┘
         │
┌────────▼────────┐
│    init.pyx     │  Unpack into ParSys struct
│                 │  psys[i].gravity_rotation_falloff = importdata[i+1][6][55]
└────────┬────────┘
         │
┌────────▼────────┐
│ structures.pyx  │  Define struct field
│                 │  float gravity_rotation_falloff
└────────┬────────┘
         │
┌────────▼────────┐
│  simulate.pyx   │  Use in calculations
│                 │  r_core = initial_rotation_falloff * r_max
└─────────────────┘
```

**Adding a new parameter requires editing ALL 6 files in this order.**

### Parameter Index Reference (params array)
```
params[50] = mol_gravity_active
params[51] = mol_gravity_strength
params[52] = mol_gravity_theta
params[53] = mol_gravity_softening
params[54] = mol_gravity_initial_rotation
params[55] = mol_gravity_rotation_falloff
```

---

## Headless Testing

Run Blender without GUI for fast iteration:

```bash
"/Applications/Blender 4.5.app/Contents/MacOS/Blender" --background --python /tmp/test_script.py
```

### Example Test Script
```python
import bpy
import sys
sys.path.insert(0, '/Users/mo/github/ucl_eye/publication_galaxy_claude/molecular-plus')

# Test addon loads
try:
    bpy.ops.preferences.addon_enable(module='molecular_plus')
    print("SUCCESS: Addon loaded")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

# Test with a blend file
bpy.ops.wm.open_mainfile(filepath="/path/to/test.blend")
# ... run simulation tests
```

### Loading a Specific Blend File
```bash
"/Applications/Blender 4.5.app/Contents/MacOS/Blender" \
    "/Users/mo/github/ucl_eye/publication_galaxy_human/gravity test.blend" \
    --background --python /tmp/debug_script.py
```

---

## Debugging Cython Code

Since you can't use Python debuggers with Cython compiled code:

### 1. Printf Debugging
```cython
from libc.stdio cimport printf

cdef void my_function() noexcept nogil:
    printf("=== FUNCTION v1.21.20 ===\n")
    printf("  parnum=%d, gravity_G=%f\n", parnum, gravity_G)
```

### 2. Version Strings
Always include a version string to confirm which code is running:
```cython
printf("=== ROTATION v1.21.20+enclosed_mass_safe ===\n")
```

This catches cases where old compiled code is cached.

### 3. Debug Counters
```cython
cdef int debug_count = 0
for i in range(parnum):
    if some_condition:
        debug_count += 1
printf("  Particles meeting condition: %d\n", debug_count)
```

---

## Lessons Learned: The State Bug

### The Problem
Rotation code wasn't applying to any particles.

### Debug Output
```
alive=0, mass_nonzero=0
P0 state=2, mass=1.000000
```

### The Bug
Code checked `if parlist[i].state >= 3` but Blender uses `state=2` for ALIVE particles.

### The Fix
Check mass instead of state:
```cython
# BAD - state values vary
if parlist[i].state >= 3:

# GOOD - mass is reliable
if parlist[i].mass > 0:
```

---

## Lessons Learned: The Crash (v1.21.19)

### Symptom
Blender got killed immediately on startup: `zsh: killed`

### Recovery
```bash
git log --oneline -10  # Find last working commit
git checkout 2a6884b -- c_sources/simulate.pyx  # Revert specific file
# Recompile and test
```

### Safe Cython Practices After This
1. **Explicit variable declarations**
   ```cython
   cdef float x = 0.0  # Not just: cdef float x
   ```

2. **Avoid compound operators in critical sections**
   ```cython
   x = x + y  # Instead of: x += y
   ```

3. **Initialize arrays before use**
   ```cython
   cdef float force[3]
   force[0] = 0.0
   force[1] = 0.0
   force[2] = 0.0
   ```

4. **Check for NULL pointers**
   ```cython
   if node == NULL:
       return
   ```

5. **Use noexcept on nogil functions**
   ```cython
   cdef void my_func() noexcept nogil:
   ```

---

## File Organization

```
molecular-plus/
├── __init__.py          # Addon registration, bl_info
├── properties.py        # All Blender property definitions
├── ui.py               # UI panels (draws the sidebar)
├── simulate.py         # Python simulation orchestration
├── operators.py        # Blender operators (buttons)
├── descriptions.py     # UI tooltip strings
├── update.py           # Update checking
├── CLAUDE_DEV_NOTES.md # This file
│
└── c_sources/
    ├── core.pyx        # Main module, includes all others
    ├── structures.pyx  # All struct definitions (Particle, ParSys, Octree, etc.)
    ├── init.pyx        # Initialization, unpacks params into structs
    ├── simulate.pyx    # Main simulation loop, gravity, rotation
    ├── octree.pyx      # Barnes-Hut octree for O(n log n) gravity
    ├── spatialhash.pyx # Spatial hashing for collision detection
    ├── link.pyx        # Particle linking logic
    ├── collide.pyx     # Collision detection/response
    ├── setup_arm64.py  # Compilation script for Apple Silicon
    │
    └── molecular_core/ # Compiled output (after build)
        └── core.cpython-311-darwin.so
```

---

## The Rotation Formula Evolution

### Attempt 1: Keplerian (Point Mass)
```
v = strength × sqrt(G × M_total / r)
```
**Problem**: Center particles moved way too fast (singularity as r→0)

### Attempt 2: Flat Rotation
```
v = constant
```
**Problem**: Galaxy collapsed too quickly

### Attempt 3: Power Law
```
v = strength × (r_max / r)^falloff
```
**Problem**: Tunable but not physically correct

### Attempt 4: Enclosed Mass (Final)
```
v = strength × sqrt(G × M_enclosed / r_effective)
r_effective = sqrt(r² + r_core²)
r_core = falloff × r_max
```
**This is physically correct for distributed mass systems.**

- `M_enclosed(r)` = sum of mass inside radius r
- Core softening prevents singularity at center
- Same technique used in N-body gravity codes

### Effect of Falloff Parameter
- **Higher falloff** (0.5-1.0+): Slower at center, minimal effect on outskirts
- **Lower falloff** (0.0-0.2): Faster at center (can explode), minimal effect on outskirts
- **Sweet spot**: Usually 0.2-0.4 for stable galaxy

---

## Compilation Details

### Why We Use External Python (not Blender's)
Blender's bundled Python lacks development headers needed for Cython compilation. We compile with Homebrew Python 3.11, but the resulting `.so` file is compatible with Blender's Python 3.11.

### Compiler Flags (from setup_arm64.py)
```python
extra_compile_args=[
    '-O3',           # Max optimization
    '-fopenmp',      # OpenMP for parallelization
    '-arch', 'arm64' # Apple Silicon
]
extra_link_args=[
    '-lomp',         # Link OpenMP runtime
    '-L/opt/homebrew/opt/libomp/lib'
]
```

### OpenMP Parallelization
The simulation uses OpenMP for parallel loops:
```cython
with nogil:
    for i in prange(parnum, schedule='dynamic', num_threads=cpunum):
        # This runs in parallel across CPU cores
```

---

## Quick Debugging Checklist

When something doesn't work:

1. **Check version string** - Is the right code loaded?
2. **Check particle count** - `printf("parnum=%d\n", parnum)`
3. **Check parameter values** - Are they being passed correctly?
4. **Check particle states** - What is `state` and `mass`?
5. **Check for crashes** - Run headless first
6. **Check compilation** - Any warnings during build?
7. **Restart Blender** - Cached imports can persist

---

## Command Line Rendering with Batching

### The Problem
Command line renders (especially long animations) can leak memory continuously, eventually consuming all RAM. On a 512GB Mac, we observed memory climbing from 70GB to 270GB+ during unbatched renders.

### The Solution
The `Render Animation (CMD)` button in the Molecular+ panel supports batched rendering. Set **Batch Size** > 0 to render in chunks, with Blender restarting between batches to free memory.

### Memory Formula

Based on empirical testing with particle simulations:

**For 2 concurrent renders:**
```
Peak Memory ≈ 70 + (batch_size ÷ step) × 3 GB
```

**For 1 render:**
```
Peak Memory ≈ 70 + (batch_size ÷ step) × 1.5 GB
```

Where:
- `batch_size` = the Batch Size setting in the UI
- `step` = scene's frame step (e.g., 128 means render every 128th frame)
- 70GB = approximate base memory for loaded scene

### Solving for Batch Size

To stay under a target memory:
```
batch_size = (target_memory - 70) ÷ 3 × step    # for 2 renders
batch_size = (target_memory - 70) ÷ 1.5 × step  # for 1 render
```

**Example:** Target 250GB max with step=128, 2 renders:
```
batch_size = (250 - 70) ÷ 3 × 128 = 7680
```

### Tested Configuration
- Batch size: 11000, Step: 128, 2 concurrent renders
- Actual peak: **338GB** (predicted: 328GB)
- Memory dropped to ~70GB between batches as expected

### UI Location
The Batch Size field appears below the "Render Animation (CMD)" button in the main Molecular+ panel. Set to 0 for no batching (renders all frames at once).

---

## Git Recovery Commands

```bash
# View recent commits
git log --oneline -10

# Revert specific file to previous commit
git checkout <commit_hash> -- path/to/file.pyx

# See what changed
git diff HEAD~1 -- path/to/file.pyx

# Stash current changes
git stash

# Apply stashed changes
git stash pop
```
