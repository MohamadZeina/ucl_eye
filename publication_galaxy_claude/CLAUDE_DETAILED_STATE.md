# CLAUDE_DETAILED_STATE.md

Blender particle position control via Python. Successfully implemented frame handler approach to set particle positions and sizes from CSV coordinates. Also compiled Molecular Plus Cython core from source for custom physics modifications. Added TSNE computation pipeline for UCL scientific literature embeddings (370K papers) with 2D/3D coordinates and field hierarchy extraction.

**Last updated**: 2026-01-09

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

## NEXT STEPS

After completing Barnes-Hut gravity:
1. Test with simple 2-body system (verify orbital mechanics)
2. Test with multi-body galaxy simulation
3. Tune parameters (θ opening angle, G constant, softening)
4. Consider adding:
   - Velocity damping option
   - Central mass attractor
   - Visualization of gravitational field
