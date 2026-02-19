# CLAUDE_DETAILED_STATE.md

Blender particle position control via Python. Successfully implemented frame handler approach to set particle positions and sizes from CSV coordinates. Also compiled Molecular Plus Cython core from source for custom physics modifications. Added TSNE computation pipeline for UCL scientific literature embeddings (370K papers) with 2D/3D coordinates and field hierarchy extraction.

**Last updated**: 2026-02-07

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
> "I would just like you to compile and run your own copy of molecular plus. Eventually, I want to be able to modify this so that we can perform kinds of physics that it wasn't designed for."

---

## CURRENT GOALS

### Goal 1: Particle Position Control from CSV ✅ COMPLETE
Programmatically set Blender particle positions from CSV without using mesh vertices.

**Status**: SOLVED. Frame handler approach works in both GUI and headless modes.

### Goal 2: Compile and Run Molecular Plus ✅ COMPLETE
Compile the Molecular Plus Cython (.pyx) files to enable custom physics modifications.

**Status**: SOLVED. Successfully compiled and installed. Addon loads in Blender 4.5.

### Goal 3: TSNE Embeddings for Scientific Literature ✅ COMPLETE
Compute TSNE dimensionality reduction for UCL scientific paper embeddings with robust metadata mapping.

**Status**: SOLVED. Generated 2D and 3D TSNE for 8K, 64K, and full 370K paper datasets with field hierarchy.

### Goal 4: Frame Integrity Verification 🟡 ANOMALY SCAN PHASE 2 — D1/D2 REMAINING
Verify all ~130,000 rendered frames across 4 drives for corruption before final compositing.

**Status (Feb 10 evening):**
- **Phase 1 (scanline corruption)**: COMPLETE across all 4 drives. 34 scanline-corrupt frames on D3, all re-rendered and verified. D1/D2/D4: 0 scanline corruption.
- **Phase 2 (subtle anomaly scan)**: Two-phase detection (file-size + oiiotool brightness/StdDev) found 152 flagged frames across all drives. Re-render and pixel-compare (old vs new) is the only reliable way to distinguish genuine corruption from natural scene variation.
- **D4 BW**: 30 flagged → re-rendered → **2 genuinely corrupt (frames 45, 8936)**, 28 natural variation. DONE.
- **D3 BW**: 72 flagged → re-rendered → **3 genuinely corrupt (frames 40683, 44325, 62178)**, 69 natural variation. DONE.
- **D2 FW**: 46 flagged → PENDING re-render (forward camera).
- **D1 FW**: 4 flagged → PENDING re-render (forward camera).
- Old originals archived to NAS: `/Volumes/Datasets Toshibas/ucl_eye/render_soft_launch/` with SHA256 manifest.

### Anomaly Detection Method
1. **Phase 1 (fast)**: Index all file sizes, flag >0.1% deviation from ±5 rolling window neighbors
2. **Phase 2 (targeted)**: `oiiotool --printstats` on flagged frames + ±3 neighbors, check brightness >0.5% and/or StdDev >0.4%
3. **Definitive test**: Stage JPG+EXR, re-render, compare old vs new with `oiiotool --diff`. Clean frames: mean_err ~1e-05 (GPU noise). Corrupt frames: mean_err >> 1.0
4. Ratio-based neighbor comparison (frame-vs-neighbor / baseline) is NOT reliable — ratios of 2-4x overlap between clean and corrupt frames

### Corrupt Frames Found So Far (5 total)
| Frame | Drive | mean_err (old vs new) | Nature |
|-------|-------|-----------------------|--------|
| 45 | D4 BW | 2.999e+07 | Zeros in Depth channel |
| 8936 | D4 BW | 2.319e+01 | Data corruption |
| 40683 | D3 BW | 3.200e+03 | Data corruption |
| 44325 | D3 BW | 2.411e+03 | Data corruption |
| 62178 | D3 BW | 1.523e+04 | Data corruption |

### Known Corruption Types (Taxonomy)

Five distinct types discovered across the 32-sample render. All apply to future renders too.

| # | Type | Detection | Severity | Cause |
|---|------|-----------|----------|-------|
| 1 | **Scanline corruption** | `oiiotool --printstats` → "unable to compute" or "corrupt" | High — visible garbled lines | Disk I/O error or write interruption during EXR save |
| 2 | **Camera flip** | `oiiotool --diff bw.exr fw.exr` → RMS < 0.01 = wrong camera | High — completely wrong frame | Blender bug: wrong camera active during batch render |
| 3 | **Subtle data corruption** | Only detectable by re-rendering and comparing old vs new (`oiiotool --diff`, mean_err >> 1.0) | Medium — may or may not be visible | Unknown — possibly GPU memory errors or race conditions |
| 4 | **Zero-size placeholders** | `os.path.getsize(f) == 0` | High — Blender skips these on restart, leaving permanent gaps | Blender crash or kill mid-frame write |
| 5 | **JPG-only (missing EXR)** | JPG exists but corresponding EXR does not | Medium — frame looks rendered but no EXR for compositing | Blender output node issue; JPG written by one output, EXR output fails silently |

**Key insight**: Types 1, 4, 5 are easy to detect automatically. Type 2 requires a reference frame from the other camera direction. Type 3 is the hardest — only detectable by re-rendering and pixel-comparing, which is expensive.

**For the new 256-sample render (17_the_one, 4 concurrent):**
- Types 4 and 5 are most likely with concurrent processes on one drive
- Recommended: periodic monitoring script checking for zero-size files, JPG/EXR count mismatches, and frame gaps

### Current Status (Feb 11)

**Old 32-sample render**: D3/D4 fully verified (5 corrupt found and fixed). D2 (46 frames) and D1 (4 frames) staged but superseded by new render.

**New 256-sample render (17_the_one)**:
- Output: `/Volumes/Mo 4TB/render/17_the_one/` (JPG) + `17_the_one_EXR/` (EXR)
- 4 concurrent Blender processes, ~32.5s/frame, ~480 frames/hr
- Target: 131,072 frames, ETA ~12.3 days
- Archival of old 32-sample render to NAS in progress (separate agent)

### Next Steps
1. Monitor new render for corruption types 4 and 5 (zero-size, missing EXR)
2. After render complete: full integrity scan (types 1-5)
3. Archive to NAS with SHA256 checksums
4. Final DaVinci export

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

## COMPLETED: MOLECULAR PLUS COMPILATION

### Summary
Successfully compiled Molecular Plus v1.21.8 Cython core from source on macOS ARM64 (Apple Silicon). The addon loads in Blender 4.5 and all core functions are accessible.

### Prerequisites Installed
1. **Python 3.11** (via Homebrew): `/opt/homebrew/bin/python3.11`
2. **Cython 3.2.4**: `pip3.11 install cython`
3. **libomp** (OpenMP): `brew install libomp`

### Source Location
```
publication_galaxy_claude/molecular-plus/     # Cloned from GitHub
├── c_sources/                                # Cython source files
│   ├── simulate.pyx                         # Main simulation logic
│   ├── collide.pyx                          # Collision detection
│   ├── spatial_hash.pyx                     # Spatial hashing
│   ├── links.pyx                            # Particle links
│   ├── init.pyx                             # Initialization
│   ├── update.pyx                           # Update functions
│   ├── memory.pyx                           # Memory management
│   ├── utils.pyx                            # Utilities
│   ├── structures.pyx                       # Data structures
│   ├── setup_arm64.py                       # ARM64 build script
│   └── setup.py                             # x86_64 build script
```

### Compilation Process

```bash
# 1. Navigate to source directory
cd publication_galaxy_claude/molecular-plus/c_sources

# 2. Run ARM64 build script (uses Homebrew Python 3.11 with Cython)
/opt/homebrew/bin/python3.11 setup_arm64.py build_ext --inplace

# Output creates:
# - molecular_core/core.cpython-311-darwin.so  (145KB ARM64 binary)
# - molecular_core/libomp.dylib                (OpenMP library)
# - molecular_core/core.c                      (Generated C code)
# - molecular_core/core.html                   (Cython annotations)
```

### Installation to Blender

```bash
# 1. Copy compiled core to Blender's site-packages
cp -r molecular_core/ "/Applications/Blender 4.5.app/Contents/Resources/4.5/python/lib/python3.11/site-packages/"

# 2. Copy addon Python files to user addons folder
mkdir -p ~/Library/Application\ Support/Blender/4.5/scripts/addons/molecular_plus
cp *.py ~/Library/Application\ Support/Blender/4.5/scripts/addons/molecular_plus/
```

### Verification

```python
# In Blender Python console or script:
from molecular_core import core
print(core.clock())        # Returns float timestamp
print(core.init)           # <cyfunction init>
print(core.simulate)       # <cyfunction simulate>
print(core.memfree)        # <cyfunction memfree>
```

**Test output**:
```
cmolcore imported  v1.21.8
core.clock() = 0.363337
core.init callable: True
core.simulate callable: True
core.memfree callable: True
```

### Key Files Created

| File | Location | Purpose |
|------|----------|---------|
| `core.cpython-311-darwin.so` | site-packages/molecular_core/ | Compiled Cython module |
| `libomp.dylib` | site-packages/molecular_core/ | OpenMP threading library |
| `molecular_plus/*.py` | ~/Library/.../addons/ | Addon Python files |

### What the Setup Script Does

1. **Concatenates all .pyx files** into single `core.pyx`
2. **Cythonizes** to generate `core.c`
3. **Compiles** with clang using ARM64 optimizations:
   - `-O3` optimization
   - `-mcpu=apple-m1` for Apple Silicon
   - `-fopenmp` for parallel processing
4. **Patches** the .so file to use `@loader_path/libomp.dylib`
5. **Copies** `libomp.dylib` alongside the .so file

### Gotchas

1. **Blender's Python lacks headers**: Blender ships minimal Python (no Python.h). Must use Homebrew Python 3.11 for compilation, then copy result to Blender's site-packages.

2. **OpenMP bundling**: macOS requires libomp.dylib to be copied alongside the .so and paths patched with `install_name_tool`.

3. **Two setup scripts**: `setup.py` is for x86_64, `setup_arm64.py` is for Apple Silicon.

4. **Wheel build fails**: The script tries to build a wheel at the end which fails (calls `python` not `python3.11`). The .so compilation succeeds before this - ignore the error.

### Backing Up Compiled Versions

**IMPORTANT**: Before making changes to Cython code, back up the current known-good compiled binary. This allows rollback if compilation breaks.

**Backup Location**: `publication_galaxy_claude/molecular-plus/compiled_backups/`

**Naming Convention**: `{module}_{platform}_{date}_{git-commit}.{ext}`
- Example: `core_macos_arm64_20260121_93ea991.so`
- Example: `core_ubuntu_x86_64_20260122_abc1234.so`
- Example: `core_windows_x86_64_20260122_abc1234.pyd`

**How to Back Up (Safe - Won't Interrupt Running Simulations)**:

```bash
# Get current commit hash and date
COMMIT_SHORT=$(git rev-parse --short HEAD)
DATE=$(date +%Y%m%d)

# Create backup directory if needed
mkdir -p publication_galaxy_claude/molecular-plus/compiled_backups

# Copy from the REPO copy (NOT from Blender's site-packages)
# This is safe even while Blender is running a simulation
cp publication_galaxy_claude/molecular-plus/molecular_core/core.cpython-311-darwin.so \
   publication_galaxy_claude/molecular-plus/compiled_backups/core_macos_arm64_${DATE}_${COMMIT_SHORT}.so

cp publication_galaxy_claude/molecular-plus/molecular_core/libomp.dylib \
   publication_galaxy_claude/molecular-plus/compiled_backups/libomp_macos_arm64_${DATE}_${COMMIT_SHORT}.dylib
```

**How to Restore**:

```bash
# Copy backup back to molecular_core/
cp compiled_backups/core_macos_arm64_20260121_93ea991.so molecular_core/core.cpython-311-darwin.so

# Then reinstall to Blender (requires Blender restart)
cp -r molecular_core/ "/Applications/Blender 4.5.app/Contents/Resources/4.5/python/lib/python3.11/site-packages/"
```

**What's Safe**:
- Copying files from the repo's `molecular_core/` folder - never touches Blender
- Creating backups in `compiled_backups/` - just file copies

**What Requires Blender Restart**:
- Copying to Blender's `site-packages/` - only do this when Blender is closed or between simulations

---

## FILE STRUCTURE

```
publication_galaxy_claude/
├── gui_script.py              # Working solution - frame handler approach
├── particles.csv              # 200-point helix with x,y,z,scale columns
├── minimal_poc_result.blend   # Test blend file (200 particles, icosphere instances)
├── CLAUDE_DETAILED_STATE.md   # This file
├── molecular-plus/            # Cloned Molecular Plus source
│   ├── c_sources/            # Cython source and build scripts
│   │   ├── *.pyx             # Cython source files
│   │   ├── setup_arm64.py    # ARM64 build script
│   │   └── molecular_core/   # Compiled output
│   └── *.py                  # Addon Python files
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

8. **Cython compilation needs standalone Python**: Blender's bundled Python lacks development headers. Use system/Homebrew Python for compilation, then copy results to Blender.

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

### 2026-01-08: Molecular Plus Compilation
- Cloned Molecular Plus from https://github.com/u3dreal/molecular-plus
- Installed prerequisites: Python 3.11, Cython 3.2.4, libomp
- Compiled ARM64 binary using setup_arm64.py
- Installed to Blender 4.5 site-packages
- Verified addon loads and core functions accessible
- All 4 core functions working: `clock`, `init`, `simulate`, `memfree`

---

## COMPLETED: HERO TRACKER BLENDER ADDON

### Purpose
Track "hero" particles through Molecular Plus simulations by creating Empty objects that follow selected particles frame-by-frame. Enables camera tracking to specific particles for cinematic shots.

### Location
- **Source**: `/Users/mo/github/ucl_eye/hero_tracker/src/__init__.py`
- **Installed**: `/Users/mo/Library/Application Support/Blender/4.5/scripts/addons/hero_tracker/`

### Version History

| Version | Features |
|---------|----------|
| v1.x-v2.x | Single camera tracking, basic baking |
| v3.0.0 | Dual-camera support - processes both FW/BW cameras in single pass |
| v3.1.0 | Frame stepping - evaluate every N frames, Blender interpolates |

### Key Features

**Dual-Camera Mode (v3.0.0)**:
- Single "Bake Hero Keyframes" operation creates Empties for both forward and backward cameras
- Each camera gets its own tracking empties (e.g., `hero_fw_0`, `hero_bw_0`)
- Required for seamless loop rendering where cameras orbit in opposite directions

**Frame Stepping (v3.1.0)**:
- Property: `frame_step` (1 = every frame, higher = faster baking)
- No hard limit on step size (soft_max=100 for UI convenience)
- Step=N gives ~Nx faster baking (e.g., step=32 for 65536-frame simulations)
- Blender interpolates between keyframes
- Always includes final frame for clean loop closure

### Failed Optimization Attempts (Documented)

**v3.2.0 - Bulk keyframe insertion using `add()` + `.co`**:
```python
# BROKEN: 500x faster but empties don't follow particles
fc.keyframe_points.add(n_keyframes)
for i, (frame, value) in enumerate(keyframes):
    fc.keyframe_points[i].co = (frame, value)
fc.update()
```
- All keyframes start at frame 0, may get merged/collapsed
- Animation visually broken despite keyframes being created

**v3.2.1 - Using `insert()` method**:
```python
# BROKEN: Same speed as v3.1.0 and still broken
fc.keyframe_points.insert(frame, value)
```
- Documented Blender API method
- Still doesn't animate objects correctly

**Lesson learned**: `object.keyframe_insert()` is slow but correct because it triggers full Blender updates. FCurve-level insertion is fast but doesn't properly register the animation. Use `frame_step` for speedups instead.

### Usage

1. Run Molecular Plus simulation with disk cache enabled
2. In Hero Tracker panel:
   - Select particle system
   - Set particle indices to track (comma-separated)
   - Set frame range and step size
   - Click "Bake Hero Keyframes"
3. Hero empties appear and follow particles through cached simulation
4. Point camera Track To constraint at hero empties

### Related: Seamless Loop Camera Drivers

For seamless loops with power-of-2 period (e.g., 65536):
```
Forward:  100 * ((frame - offset) / period)
Backward: 100 * (-(frame - offset) / period)
```

Meeting frames: {offset, period/2 + offset, period + offset}

Use offset to skip artefact frames (e.g., offset=4 to skip frames 0-3).

---

## CURRENT GOAL: BARNES-HUT GRAVITY SIMULATION (Goal 3)

### Objective
Add gravitational attraction between particles using the Barnes-Hut algorithm. Create "Molecular Plus Plus" - a modified version of Molecular Plus with N-body gravity simulation for galaxy/planetary simulations.

### User Requirements (Exact Quotes)
> "I'd like you to create a modified version of Molecular Plus, which we'll call Molecular Plus Plus. Where we add in a gravity simulation, meaning that I can disable gravity in Blender and simulate each of these particles as a star or a planet or some planetary body that are attracted to each other."
>
> "This should be a new tab in the Molecular add-on... We should add one for Gravity, which is disabled by default, but can be enabled just like the normal collisions can be."
>
> "Let's go with the fancy algorithm [Barnes-Hut]... implement this other gravity simulation feature on the latest version of molecular plus."
>
> "Don't create billions of new files, keep your changes to an absolute minimum."

### Why Barnes-Hut (Not Brute Force or KNN)
- **Brute force**: O(n²) - too slow for >1000 particles
- **KNN (K-nearest)**: Ignores distant particles completely - physically wrong
- **Barnes-Hut**: O(n log n) - treats distant particle groups as single point masses at their center of mass. Physically accurate approximation.

### Algorithm Overview
1. Build **octree** of all particles each frame
2. For each node, precompute **total mass** and **center of mass**
3. For each particle, traverse tree:
   - If `node_size / distance < θ` (opening angle): treat node as single mass
   - Otherwise: recurse into children
4. Apply gravitational force: `F = G × m1 × M_node / r²`

### Implementation Plan (Minimal Changes)
| File | Change |
|------|--------|
| `structures.pyx` | Add `Octree` and `OctreeNode` structs ✅ DONE |
| `simulate.pyx` | Add Barnes-Hut functions and gravity step |
| `init.pyx` | Unpack gravity parameters |
| `simulate.py` | Pass gravity settings to core |
| `properties.py` | Add gravity properties (`mol_gravity_active`, etc.) |
| `ui.py` | Add "Gravity" UI section |

### Key Discovery: Particle Mass Already Exists
The `Particle` struct already has a `mass` field (structures.pyx:107). The "Calculate Particle Weight by Density" feature uses this:

```python
# From simulate.py lines 116-125
if psys.settings.mol_density_active:
    par_mass = density × (4/3 × π × (size/2)³)  # Spherical volume × density
else:
    par_mass = psys.settings.mass  # Same mass for all
```

**Key insight**: Particles with different SIZES get different MASSES when density mode is enabled. This is perfect for galaxy simulations - larger stars = more mass = stronger gravity.

### Status
- [x] Examined particle data structures
- [x] Understood simulation architecture
- [x] Added `Octree` and `OctreeNode` structs to structures.pyx
- [ ] Implement Barnes-Hut functions in simulate.pyx
- [ ] Add gravity properties to properties.py
- [ ] Add gravity UI section to ui.py
- [ ] Update init.pyx to unpack gravity params
- [ ] Update simulate.py to pass gravity params
- [ ] Compile and test

### CRITICAL TECHNICAL DETAILS (Preserve for Compaction)

#### Data Flow: Blender → Cython
1. `simulate.py:pack_data()` collects Blender particle data into arrays
2. Creates `params` list (currently 50 elements, indices 0-49)
3. Passes to `core.init(importdata)` on first frame
4. Passes to `core.simulate(importdata)` each subsequent frame

#### params Array Structure (simulate.py lines 175-226)
```
params[0] = mol_selfcollision_active
params[1] = mol_othercollision_active
params[2] = mol_collision_group
params[3] = mol_friction
params[4] = mol_collision_damp
params[5] = mol_links_active
... (up to index 49)
params[48] = mol_collision_adhesion_search_distance
params[49] = mol_collision_adhesion_factor
# ADD GRAVITY AT: params[50], params[51], params[52]
```

#### Simulation Loop (simulate.pyx:simulate())
```
1. update(importdata)           # Updates particle state from Blender
2. Copy particles to parlistcopy
3. SpatialHash_build()          # For collision detection
4. SpatialHash_query_neighbors() # Find nearby particles (parallel)
5. collide() + solve_link()     # Per-particle physics
6. Export data back to Blender
```
**INSERT GRAVITY AFTER step 4, BEFORE step 5**

#### Key Global Variables (simulate.pyx)
```cython
cdef Particle *parlist = NULL      # All particles
cdef int parnum = 0                # Particle count
cdef float deltatime = 0           # Time step
cdef int cpunum = 0                # Thread count
```

#### Particle Struct (structures.pyx:102-121)
```cython
cdef struct Particle:
    int id
    float loc[3]      # Position
    float vel[3]      # Velocity - MODIFY THIS FOR GRAVITY
    float size
    float mass        # ALREADY EXISTS - use for gravity!
    int state
    ...
```

#### Changes Made So Far
1. **structures.pyx**: Added at end of file:
   - `OctreeNode` struct (center, half_size, mass, com, children[8])
   - `Octree` struct (root, node_pool, theta, G, softening)

#### Files to Modify (In Order)
1. `properties.py` - Add: `mol_gravity_active`, `mol_gravity_strength`, `mol_gravity_theta`, `mol_gravity_softening`
2. `ui.py` - Add "Gravity" box section after "Collisions" section (around line 416)
3. `simulate.py` - Add params[50-53] for gravity settings
4. `init.pyx` - Unpack gravity params into global variables
5. `simulate.pyx` - Add Barnes-Hut functions:
   - `Octree_create()`, `Octree_destroy()`
   - `Octree_insert_particle()`
   - `Octree_compute_mass_distribution()`
   - `Octree_calculate_force()`
   - Call from within `simulate()` after neighbor query

#### Barnes-Hut Algorithm Pseudocode
```
def apply_gravity():
    # Build octree
    octree = Octree_create(parnum)
    for i in range(parnum):
        Octree_insert_particle(octree, &parlist[i])
    Octree_compute_mass_distribution(octree.root)

    # Calculate forces (parallel)
    for i in prange(parnum):
        force = Octree_calculate_force(octree.root, &parlist[i], theta)
        # F = ma, a = F/m, v += a*dt
        parlist[i].vel[0] += force[0] / parlist[i].mass * deltatime
        parlist[i].vel[1] += force[1] / parlist[i].mass * deltatime
        parlist[i].vel[2] += force[2] / parlist[i].mass * deltatime

    Octree_destroy(octree)
```

#### Opening Angle θ (theta)
- `θ = node_size / distance_to_node`
- If θ < threshold (0.5-1.0): treat node as single point mass
- Smaller θ = more accurate but slower
- θ = 0.5 is typical for galaxy simulations

#### To Answer User's Question About Density
YES, "Calculate Particle Weight by Density" gives different particles different masses based on their SIZE:
```python
mass = density × (4/3 × π × (radius)³)
```
Larger particles = larger volume = more mass. Perfect for galaxy simulations where star size correlates with mass.

---

## COMPLETED: TSNE SCIENTIFIC LITERATURE EMBEDDINGS

### The Task
Compute TSNE dimensionality reduction for ~370K UCL scientific paper abstracts, with robust mapping to metadata including research field hierarchy.

### Data Sources
- **Embeddings**: BAAI-bge-large-en embeddings (1024 dims) for 418.9K paper title+abstracts
- **Metadata**: OpenAlex data with DOIs, citations, publication year, concepts (field hierarchy)
- **Location**: `/mnt/wwn-0x5000c500d577b928/mo_data/datasets/`

### Generated Outputs
All saved to `/mnt/wwn-0x5000c500d577b928/mo_data/models_etc/tsne/`:

| Dataset | Dims | Papers | File |
|---------|------|--------|------|
| 8K | 2D | 8,000 | `ucl_papers_tsne_mapping_8K.csv` |
| 64K | 2D | 64,000 | `ucl_papers_tsne_mapping_64K.csv` |
| Full | 2D | 369,766 | `ucl_papers_tsne_mapping.csv` |
| 8K | 3D | 8,000 | `ucl_papers_tsne_mapping_8K_3D.csv` |
| 64K | 3D | 64,000 | `ucl_papers_tsne_mapping_64K_3D.csv` |
| Full | 3D | 369,766 | `ucl_papers_tsne_mapping_full_3D.csv` |

### CSV Columns
- `cleaned_title` - Paper title
- `decoded_abstract` - Full abstract text
- `tsne_x`, `tsne_y`, `tsne_z` (3D only) - TSNE coordinates
- `raw_doi`, `doi` - DOI identifiers
- `publication_year` - Year published
- `cited_by_count`, `citations_per_year` - Citation metrics
- `field_level_0` - Broadest field (e.g., "Medicine", "Computer Science")
- `field_level_1` - Sub-field
- `field_level_2` - Specific area
- `type`, `language`

### Code Architecture

**`tsne_module.py`** - Reusable module with functions:
- `load_tsne_data(n_samples=None)` - Load pre-computed TSNE from CSV
- `visualize_tsne(df, color_by=..., ...)` - Scatter plot visualization
- `visualize_tsne_heatmap(df, ...)` - Density heatmap
- `compute_tsne_from_embeddings(...)` - Generate new TSNE
- `extract_field_from_concepts(concepts, level)` - Extract field hierarchy
- `save_tsne_results(...)` - Save with metadata

**`compute_tsne.py`** - Script using the module (with `# %%` cell markers for interactive use)

### TSNE Parameters Used
- Perplexity: 40
- Iterations: 1000
- PCA pre-reduction: 1024 → 50 dimensions (faster, similar results)
- Random state: 42 (reproducible)

### Key Insight from Original Notebook
The original `tsne.ipynb` had a bug where `duplicate_indices` computed from one embedding file were incorrectly applied to TSNE results from a different embedding file. This caused ~49K row misalignment. The new pipeline properly deduplicates and maintains alignment throughout.

---

## FIELD LEVEL 1 MAPPING (OpenAlex Concepts)

The TSNE datasets use OpenAlex concept hierarchy. Below are the 284 unique `field_level_1` values, grouped by their primary `field_level_0` parent (based on most frequent occurrence in the UCL dataset).

### Art (4 fields)
- Art history
- Humanities
- Literature
- Visual arts

### Biology (18 fields)
- Agronomy
- Andrology
- Biotechnology
- Botany
- Cancer research
- Cell biology
- Computational biology
- Ecology
- Endocrinology
- Evolutionary biology
- Genetics
- Horticulture
- Microbiology
- Molecular biology
- Toxicology
- Veterinary medicine
- Virology
- Zoology

### Business (16 fields)
- Accounting
- Actuarial science
- Advertising
- Agricultural economics
- Agricultural science
- Business administration
- Commerce
- Environmental economics
- Environmental planning
- Finance
- Financial system
- Industrial organization
- International trade
- Marketing
- Natural resource economics
- Process management

### Chemistry (20 fields)
- Biochemistry
- Biophysics
- Chromatography
- Combinatorial chemistry
- Computational chemistry
- Crystallography
- Food science
- Inorganic chemistry
- Medicinal chemistry
- Molecular physics
- Nuclear chemistry
- Nuclear magnetic resonance
- Organic chemistry
- Photochemistry
- Physical chemistry
- Polymer chemistry
- Pulp and paper industry
- Radiochemistry
- Stereochemistry
- Thermodynamics

### Computer science (54 fields)
- Acoustics
- Algorithm
- Arithmetic
- Artificial intelligence
- Automotive engineering
- Biochemical engineering
- Biological system
- Computational science
- Computer architecture
- Computer engineering
- Computer graphics (images)
- Computer hardware
- Computer network
- Computer security
- Computer vision
- Control engineering
- Data mining
- Data science
- Database
- Distributed computing
- Electrical engineering
- Electronic engineering
- Embedded system
- Engineering drawing
- Engineering management
- Human–computer interaction
- Industrial engineering
- Information retrieval
- Internet privacy
- Knowledge management
- Machine learning
- Management science
- Manufacturing engineering
- Mathematical optimization
- Mechanical engineering
- Multimedia
- Natural language processing
- Operating system
- Operations research
- Parallel computing
- Process engineering
- Programming language
- Real-time computing
- Reliability engineering
- Remote sensing
- Risk analysis (engineering)
- Simulation
- Software engineering
- Speech recognition
- Systems engineering
- Telecommunications
- Theoretical computer science
- Transport engineering
- World Wide Web

### Economics (17 fields)
- Classical economics
- Demographic economics
- Econometrics
- Economic policy
- Economic system
- Financial economics
- International economics
- Keynesian economics
- Labour economics
- Macroeconomics
- Market economy
- Mathematical economics
- Microeconomics
- Monetary economics
- Neoclassical economics
- Public economics
- Welfare economics

### Engineering (6 fields)
- Aeronautics
- Architectural engineering
- Civil engineering
- Construction engineering
- Forensic engineering
- Marine engineering

### Environmental science (11 fields)
- Agricultural engineering
- Atmospheric sciences
- Climatology
- Environmental chemistry
- Environmental engineering
- Environmental protection
- Meteorology
- Petroleum engineering
- Soil science
- Waste management
- Water resource management

### Geography (9 fields)
- Agroforestry
- Archaeology
- Cartography
- Economic geography
- Environmental resource management
- Fishery
- Forestry
- Regional science
- Socioeconomics

### Geology (12 fields)
- Earth science
- Geochemistry
- Geodesy
- Geomorphology
- Geotechnical engineering
- Mineralogy
- Mining engineering
- Oceanography
- Paleontology
- Petrology
- Physical geography
- Seismology

### History (4 fields)
- Ancient history
- Classics
- Ethnology
- Genealogy

### Materials science (13 fields)
- Biomedical engineering
- Chemical engineering
- Chemical physics
- Composite material
- Condensed matter physics
- Engineering physics
- Metallurgy
- Nanotechnology
- Nuclear engineering
- Optics
- Optoelectronics
- Polymer science
- Structural engineering

### Mathematics (7 fields)
- Applied mathematics
- Combinatorics
- Discrete mathematics
- Geometry
- Mathematical analysis
- Pure mathematics
- Statistics

### Medicine (41 fields)
- Anatomy
- Anesthesia
- Animal science
- Bioinformatics
- Cardiology
- Demography
- Dentistry
- Dermatology
- Emergency medicine
- Environmental health
- Family medicine
- Gastroenterology
- General surgery
- Gerontology
- Gynecology
- Immunology
- Intensive care medicine
- Internal medicine
- Library science
- Medical education
- Medical emergency
- Medical physics
- Nuclear medicine
- Nursing
- Obstetrics
- Oncology
- Operations management
- Ophthalmology
- Optometry
- Orthodontics
- Pathology
- Pediatrics
- Pharmacology
- Physical medicine and rehabilitation
- Physical therapy
- Physiology
- Psychiatry
- Radiology
- Surgery
- Traditional medicine
- Urology

### Philosophy (1 field)
- Theology

### Physics (16 fields)
- Aerospace engineering
- Astrobiology
- Astronomy
- Astrophysics
- Atomic physics
- Classical mechanics
- Computational physics
- Geophysics
- Mathematical physics
- Mechanics
- Nuclear physics
- Particle physics
- Quantum electrodynamics
- Quantum mechanics
- Statistical physics
- Theoretical physics

### Political science (9 fields)
- Development economics
- Economic growth
- Economic history
- Economy
- Law
- Law and economics
- Political economy
- Public administration
- Public relations

### Psychology (14 fields)
- Applied psychology
- Audiology
- Clinical psychology
- Cognitive psychology
- Cognitive science
- Communication
- Criminology
- Developmental psychology
- Linguistics
- Mathematics education
- Neuroscience
- Psychoanalysis
- Psychotherapist
- Social psychology

### Sociology (12 fields)
- Aesthetics
- Anthropology
- Engineering ethics
- Environmental ethics
- Epistemology
- Gender studies
- Management
- Media studies
- Pedagogy
- Positive economics
- Religious studies
- Social science

---

## RENDER INTEGRITY ANALYSIS (2026-02-06/07, updated Feb 7 night)

### Overview
Built and ran a frame integrity checker across ~130,000 frames of the final 8K seamless loop render, split across four external drives. Found both isolated corruptions and a systematic camera flip in backward renders. Camera was fixed and corrected renders are in progress.

### Drive Layout & Frame Inventory (as of Feb 7 ~23:30)

| Drive | Direction | Frame Range | JPGs | EXRs | Status |
|-------|-----------|-------------|------|------|--------|
| Mo 4TB | Forward | 50063→65803 | ~15,741 | ~15,741 | Complete |
| Mo 4TB 2 | Forward | 4→50062 | 50,059 | 50,059 | Complete |
| Mo 4TB 3 | Backward | 22,666→66,000 | 22,535 | 20,717 | Active rendering (4 frontiers) |
| Mo 4TB 4 | Backward | 4→22,664 | 22,661 | 22,661 | Complete (step-1) |

**Forward pass**: Complete. ~65,800 frames total across Drives 1+2.
**Backward pass**: Drive 4 complete at step-1. Drive 3 actively rendering with 4 step-1 frontiers.

### Frame Integrity Checker

**Script**: `/Users/mo/github/ucl_eye/frame_integrity_check/check_frames.py`
**Environment**: `/opt/anaconda3/envs/pytorch/` (numpy, Pillow, scipy, matplotlib)
**Results**: `/Users/mo/github/ucl_eye/frame_integrity_check/results/` (gitignored)

**Methodology**:
- Compares adjacent frames using multiple metrics
- Downscale factor 16 (8K → ~500px) — sufficient for corruption detection
- Metrics: Mean Absolute Difference (MAD), max block difference, histogram chi-squared, correlation coefficient, dark pixel ratio, brightness, standard deviation
- Anomaly detection: Median + MAD-based robust statistics (scaled by 1.4826), 5-sigma threshold
- Throttled mode (1 worker, 0.05s sleep) to avoid interfering with active renders

**Usage**:
```bash
# Scan specific range
/opt/anaconda3/envs/pytorch/bin/python check_frames.py \
  /Volumes/Mo\ 4TB\ 2/render/16_final_path_fw_no_hero \
  --range 4 50062 --throttle 0.05 --workers 1

# Scan all known ranges
/opt/anaconda3/envs/pytorch/bin/python check_frames.py --scan-all --throttle 0.05
```

### Finding 1: Wrong Camera in Backward Render (CRITICAL — CAMERA FIXED, RE-RENDERING)

The backward render on Drive 3 had the **forward camera active** for a large batch of step-2 and some step-1 fills. These frames were pixel-identical to the forward render.

**Detection methods developed (in order of reliability)**:
1. **oiiotool --diff pixel comparison** (definitive): Compare BW frame against FW at same frame number. RMS < 0.01 = identical = wrong camera. RMS ~0.36-0.46 = correct (different orbit positions).
2. **Pixel correlation**: Wrong-camera frames have corr > 0.99. Correct frames corr ~0.1-0.3.
3. **File size comparison**: Step-2 fills rendered with wrong camera are larger (~71-78 MB EXR) vs correct BW step-4 frames (~37-47 MB). Only catches ~40% of cases.
4. **mtime analysis**: JPG-EXR mtime difference of 0.1-0.3s indicates simultaneous write (same render pass).

**Flip boundary**: Frame 31024 (last correct step-2) → 31026 (first flipped step-2). All step-2 fills from 31026-65998 were flipped.

**Wrong-camera frames found: ~9,183 total**

| Step | Range | Count | Notes |
|------|-------|-------|-------|
| Step-2 | 31026 → 65998 | 8,744 | Contiguous block |
| Step-1 | 22665 → 22669 | 3 | Isolated boundary |
| Step-1 | 25711 → 25861 | 76 | Contiguous block |
| Step-1 | 30005 → 30231 | 114 | Render frontier |
| Step-1 | 32557 → 32737 | 91 | Render frontier |
| Step-1 | 36901 → 36985 | 43 | Render frontier |
| Step-1 | 40005 → 40231 | 114 | Render frontier |
| Step-2 | 22670 | 1 | Isolated straggler |

**Deletion details**: A previous agent deleted both JPG and EXR for flipped frames in most cases. The deletion was verified by checking untouched ranges (e.g., frames 45002-45046 between frontiers): these step-2 fills have NEITHER JPG nor EXR, confirming both were deleted.

**Blender skip/overwrite behavior** (confirmed via mtime and pixel analysis):
- Blender checks for **JPG** to decide whether to skip a frame
- Missing JPG → Blender renders the frame and writes both JPG and EXR
- Present JPG → Blender skips entirely (does not re-render)
- When re-rendering, Blender DOES overwrite existing EXR files

**Camera was fixed** and all four active render frontiers confirmed rendering with correct backward camera.

**What we initially thought was "cache degradation"** (step-4 BW frames appearing dim at 32K-66K) is actually the **legitimate backward camera view** — the backward orbit passes through a region with fewer visible particles, so lower brightness is expected. Step-2 fills appeared "brighter" only because they were secretly forward-camera frames.

### Finding 2: Corrected Renders Missing EXR for Step-2 Fills (NEW — Feb 7)

The corrected step-1 renders write JPGs for ALL frames they encounter, but **do NOT write EXR for step-2 fill frames**. Odd (step-1) frames get both JPG and EXR.

**Evidence** (frames 31025-31035, all rendered ~9.3h ago by corrected renders):
- 31025 (odd): JPG + EXR (101.5 MB) ✓
- 31026 (step-2): JPG only, NO EXR ✗
- 31027 (odd): JPG + EXR (101.5 MB) ✓
- 31028 (step-4): JPG + EXR (101.4 MB, from original 91h ago) ✓
- 31029 (odd): JPG + EXR (101.5 MB) ✓
- 31030 (step-2): JPG only, NO EXR ✗

**Scope**: 1,722 step-2 fill frames on Drive 3 have JPG but no EXR.

**Hypothesis**: The batch rendering script configuration may not include the EXR compositor output node for re-renders, or there's a file output node configuration issue in Blender.

**Impact**: After all JPG rendering completes, a second pass will be needed to generate EXRs for these ~1,722 frames (plus any additional step-2 fills re-rendered by the current frontiers going forward). Alternatively, fix the render configuration to produce EXR and re-render just these frames.

### Finding 3: Isolated Corrupted Frames (7 total, NOT deleted)

Individual frames with correct camera but wrong render output (batch boundary glitches):

| Frame | Drive | Direction | Issue | Brightness vs Expected |
|-------|-------|-----------|-------|----------------------|
| 2697 | Mo 4TB 4 | BW | Too bright | 65 vs ~40 |
| 23270 | Mo 4TB 3 | BW | Too dim | ~18 vs ~30 |
| 25005 | Mo 4TB 3 | BW | Corrupted | Statistical anomaly |
| 25707 | Mo 4TB 3 | BW | Too dim | 24.6 vs 32.0 |
| 55680 | Mo 4TB 3 | BW | Too bright | 20.7 vs 8.5 (step-4 batch boundary) |
| 23430 | Mo 4TB 2 | FW | Too bright | Missing shadows/AO |
| 24970 | Mo 4TB 2 | FW | Too bright | Missing shadows/AO |

**These still exist on disk** and need individual re-rendering.

### Finding 4: Forward Renders Clean

Both forward drives confirmed consistent and correct:
- Drive 1 FW (50063→65803): No anomalies
- Drive 2 FW (4→50062): 2 isolated corruptions (23430, 24970) only

### Finding 5: No Non-Sequential Rendering Artifacts

Comprehensive artifact analysis across all regions found:
- **No brightness flicker** between step types: step-4, step-2, step-1 match within 0.03 brightness
- **No step-boundary correlation drops** (except natural scene dynamics in high-motion regions)
- **D3/D4 drive boundary**: Clean transition, no discontinuity
- The step-4 BW brightness profile (dim at 40K-60K) is the genuine backward camera view

### Active Render Status (Feb 8 ~00:10)

4 concurrent Blender processes rendering step-1, advancing forward on Drive 3:

| Frontier | Current Frame | Advancing Toward |
|----------|--------------|-----------------|
| 1 | ~29,787 | → 66,000 |
| 2 | ~33,389 | → 66,000 |
| 3 | ~43,367 | → 66,000 |
| 4 | ~53,151 | → 66,000 |

**Speed**: ~585-749 frames/hr (4 concurrent, step-1, batch size 64)

### Exhaustive Wrong-Camera Re-check (Feb 8 ~00:00, DEFINITIVE)

Checked ALL remaining step-2 frames in the 31026-65998 danger zone and ALL step-1 frames in original wrong ranges on D3 using /32 pixel correlation:

| Check | Frames Checked | Wrong Found | Notes |
|-------|---------------|-------------|-------|
| Step-2 in 31026-65998 | 1,785 | 2 (false positives) | 32770, 32774 — within 2 frames of meeting point 32772 |
| Step-1 in original wrong ranges | 91 | 0 | All correct |
| Frame 33182 (flagged by other agent) | 1 | 0 | corr=0.497 — correct backward camera |

**Frames 32770 and 32774**: Almost certainly false positives. At 2 frames from the meeting point (32772), the FW and BW cameras are only 0.011° apart. Their correlation of 0.997 is far below the definitive wrong-camera threshold (0.99998+). However, the auto-delete script removed their JPGs. Blender will re-render them when a frontier passes. No harm done.

**Frame 33182**: CONFIRMED CORRECT. The other agent's concern was unfounded — this frame was already re-rendered with the correct backward camera before frontier 2 passed it.

**VERDICT: Zero wrong-camera frames remain on disk.** The original 9,183 deletion plus frame 22670 straggler was sufficient.

### Gap Analysis (Feb 8 ~00:10)

**Gaps BEHIND all frontiers (will NOT be covered by current renders):**

| Frames | Count | Issue |
|--------|-------|-------|
| 22,667, 22,669 | 2 | Odd frames at D3/D4 boundary, deleted wrong-camera |
| 22,670 | 1 | Even (step-2) at boundary, deleted wrong-camera |
| 25,711-25,861 | 76 | Contiguous odd block, deleted wrong-camera |
| **Total** | **79** | Need separate render |

**Gaps AHEAD of frontiers (will be covered as renders advance):**

| Type | Approx Count | Notes |
|------|-------------|-------|
| Deleted step-2 fills (31026→65998) | ~6,961 | Both JPG+EXR deleted, re-rendered when frontier passes |
| 32770, 32774 | 2 | JPGs deleted by false-positive check, re-rendered when frontier passes |
| Missing odd frames | ~12,000+ | Never rendered yet, created when frontier passes |
| **Total** | ~19,000+ | Covered by current 4 frontiers advancing to 66,000 |

**Frame list saved to**: `/Users/mo/github/ucl_eye/frame_integrity_check/wrong_camera_frames.json`

### Lessons Learned

1. **Always verify camera selection before batch renders**: The backward render silently used the forward camera for step-2/step-1 fills. Cross-reference a sample against the other pass immediately.
2. **oiiotool --diff is the definitive wrong-camera test**: `oiiotool --diff frame_bw.exr frame_fw.exr` → RMS < 0.01 means identical (wrong camera). File size comparison only catches ~40%.
3. **Don't assume "degradation" without cross-checking**: What looked like progressive cache fade-to-black was actually the correct backward view — the "bright" step-2 fills were the wrong camera.
4. **Blender skip logic checks JPG, not EXR**: Delete only the JPG to force re-render. Both JPG and EXR get rewritten.
5. **Check BOTH JPG and EXR when verifying deletions**: A previous agent deleted JPGs but missed EXRs for some frames. Always verify both file types.
6. **Throttle I/O during active renders**: Use `--throttle 0.05 --workers 1`.
7. **macOS `._` files**: Filter with `not name.startswith('.')`.
8. **Verify EXR output after re-renders**: The corrected step-1 renders wrote JPGs but missed EXRs for step-2 fill frames. Always check both outputs after a re-render pass.

---

## COMPLETED: MOLECULAR PLUS BATCHED RENDERING

### The Problem
Blender's Molecular Plus plugin leaks memory during long command-line renders, eventually causing crashes or degraded output.

### Solution
`simulate.py` was modified to add `--batch-size N` CLI argument that:
1. Renders N frames at a time
2. Saves to disk cache
3. Restarts Blender between batches
4. Wrapper shell script orchestrates the batch loop

### Memory Formula
For Molecular Plus simulations:
```
Memory ≈ N_particles × N_cached_frames × 200 bytes
```
At 370K particles × 65536 frames × 200 bytes ≈ 4.5 TB (impossible to cache fully)
→ Must use disk cache + shorter batch windows

---

## EXR SCANLINE CORRUPTION (Feb 9-10, ACTIVE)

### The Problem
DaVinci Resolve "media offline" errors at specific timecodes during export. JPG proxies look fine — corruption is **EXR-only** (corrupted/missing scanline chunks). The JPG-based `check_frames.py` scanner cannot detect this.

### Detection Method
1. **DaVinci Resolve export**: Fails at specific timecodes with "media offline"
2. **Timecode → frame mapping**: TC (MM:SS:FF at 60fps) → symlink index → actual frame number
   - If DaVinci shows HH:MM:SS:FF with leading `01:`, subtract 1 hour first
   - Index = `(MM * 60 + SS) * 60 + FF`
   - Symlink dir: `/Volumes/Mo 4TB/render/seamless_loop_step1_EXR_100pct/`
   - Frame offset: symlink index + 4 (due to offset in symlink generator)
3. **oiiotool confirmation** (DEFINITIVE): `oiiotool frame.exr --printstats`
   - Corrupt: `"unable to compute: Some scanline chunks were missing or corrupted"`
   - Clean: prints stats without error
   - Takes ~2 sec per 8K 14-channel EXR
4. **Always check adjacent frames** (corruption sometimes spans 2+ consecutive frames)

### Scan Script
`/tmp/exr_scan.py` — parallel oiiotool --printstats across all EXRs, 3 workers per drive. At ~2 sec/frame with 3 workers, D1 (15K EXRs) takes ~2.5 hours. Full 130K scan ~18 hours.

### Key Insights
1. JPG and EXR are written by separate Blender output nodes. EXR corruption does NOT affect the JPG — the JPG can look pixel-perfect while the EXR has corrupted scanline chunks. This is likely a write-time I/O issue (disk contention during concurrent renders).
2. **DaVinci does NOT always catch corruption.** Sometimes DaVinci silently renders a corrupt/missing frame instead of showing "media offline". This means DaVinci export alone is NOT sufficient — **exhaustive oiiotool scan of every EXR is mandatory**.
3. Corruption on D3 BW is widespread (80+ frames across 23K-64K range) and often appears in clusters spaced exactly 4 frames apart (step-2 pattern), suggesting batch-boundary corruption during original renders.

### Deletion Protocol
When confirmed corrupt: delete BOTH JPG and EXR. Blender checks for JPG to decide skip/render, so deleting JPG forces re-render of both.

### Corrupt Frames Found (cumulative, Feb 10)

**D2 FW (Mo 4TB 2) — ALL CLEAN:**
| Frame | TC | Found by | Status |
|-------|----|----------|--------|
| 32772 | 06:34:43 | DaVinci | Re-rendered, verified |
| 23687 | — | DaVinci | Re-rendered, verified |
| 24964 | — | DaVinci | Re-rendered, verified |
| 43908 | 12:11:44 | DaVinci | Re-rendered, verified |
| 48132 | 13:22:08 | DaVinci | Re-rendered, verified |

**D1 FW (Mo 4TB) — ALL CLEAN:**
| Frame | TC | Found by | Status |
|-------|----|----------|--------|
| 51076 | 14:11:12 | DaVinci | Re-rendered, verified |
| 51077 | 14:11:13 | Adjacent check | Re-rendered, verified |
| 53764 | 14:56:00 | DaVinci | Re-rendered, verified |
| 59012 | 16:23:28 | DaVinci | Re-rendered, verified |
| 59652 | 16:34:08 | DaVinci | Re-rendered, verified |

**D1 FW exhaustive scan: 14,723 EXRs checked, 0 corrupt. D1 CLEAN.**

**D3 BW (Mo 4TB 3) — AWAITING RE-RENDER:**

Frames found via DaVinci TC + adjacent checks (JPG+EXR already deleted):
36245, 36246, 36269, 37765, 37766, 37767, 37794, 37801, 37802,
47327, 47407, 47540, 47637, 47639, 48553, 48555, 48602, 48605,
48615, 48618, 48943, 49719, 49730, 49777, 56660, 59183, 59187,
59191, 59668, 59934, 59938, 60379, 60383, 60387, 60391, 60742,
60944, 61478, 61482, 61486, 61490, 61861, 61865, 62031, 62035,
62245, 62375, 62379, 63382, 63386, 64024
**(51 frames, range 36245→64024)**

Frames found by background oiiotool scan (EXR still on disk, JPG needs deletion before render):
23146, 23266, 23274, 23393, 23450, 23489, 23493, 23894, 23902,
23938, 23958, 24161, 24165, 24450, 24501, 24510, 24514, 24518,
24522, 24547, 24551, 24653, 24657, 24658, 25001, 25053, 25154,
25341, 25435, 25439, 25555, 25612, 25690, 25694
**(34+ frames so far, scan only 8% complete on D3)**

**D3 BW + D4 BW (35676):**
| Frame | Found by | Status |
|-------|----------|--------|
| 35676 | DaVinci | Re-rendered, verified |

### Observations
- **D3 BW has the vast majority of corruption** — 85+ frames found so far
- D1 FW and D2 FW are now fully clean after re-renders
- Corruption often comes in pairs/clusters spaced 4 frames apart (step-2 batch boundaries)
- Sometimes 3+ consecutive frames corrupt (37765-37767)
- Corruption spans entire D3 range (23K-64K) — not localized

### Completed Scans (Feb 10)
- **D1 FW**: 14,723 EXRs, 0 scanline corrupt. 4 anomaly-flagged, PENDING re-render.
- **D2 FW**: 50,059 EXRs, 0 scanline corrupt. 46 anomaly-flagged, PENDING re-render.
- **D3 BW**: ~43K EXRs, 34 scanline corrupt (all re-rendered). 72 anomaly-flagged → re-rendered → 3 genuine corrupt FIXED.
- **D4 BW**: 22,650 EXRs, 0 scanline corrupt. 30 anomaly-flagged → re-rendered → 2 genuine corrupt FIXED.

### NAS Archive
Old originals from anomaly re-renders archived to:
`/Volumes/Datasets Toshibas/ucl_eye/render_soft_launch/`
- `D4_BW_staging_anomaly/` — 30 JPG + 30 EXR (SHA256 verified)
- `D3_BW_staging_anomaly/` — 72 JPG + 72 EXR (SHA256 verified)
- `copy_manifest.json` — full SHA256 checksums

---

## NEXT STEPS

### Immediate (Feb 10 evening)
1. **Stage D2 FW** (46 frames, forward camera) — biggest remaining batch
2. **Stage D1 FW** (4 frames, forward camera) — can do same Blender session as D2
3. Re-render both, compare old vs new, identify genuine corruption
4. Archive old originals to NAS, delete staging from DAS
5. Regenerate symlink sequences: `python3 symlink_sequence.py --step 1`
6. Final DaVinci export

### Barnes-Hut Gravity (On Hold)
After completing Barnes-Hut gravity:
1. Test with simple 2-body system (verify orbital mechanics)
2. Test with multi-body galaxy simulation
3. Tune parameters (θ opening angle, G constant, softening)
4. Consider adding:
   - Velocity damping option
   - Central mass attractor
   - Visualization of gravitational field
