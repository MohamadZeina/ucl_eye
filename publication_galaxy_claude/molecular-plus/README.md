# Molecular Plus Plus - Extended Particle Solver for Blender 4.5+

A fork of [u3dreal/molecular-plus](https://github.com/u3dreal/molecular-plus) with additional features for scientific visualization.

## New Features in This Fork

### 1. Barnes-Hut N-Body Gravity
- O(n log n) gravitational simulation using octree spatial partitioning
- Configurable parameters: strength, accuracy (theta), softening
- Works with particle mass/density settings

### 2. CSV Initial Positions
- Load particle positions from CSV files (x, y, z columns)
- Supports TSNE output files (tsne_x, tsne_y, tsne_z)
- Particles are positioned at CSV coordinates on frame 1

### 3. CSV-Based Particle Sizes
- Scale particles based on CSV column values (e.g., cited_by_count)
- **Scale modes**: RADIUS (linear) or VOLUME (cube root for mass representation)
- **Min Scale**: Prevents zero-size particles (e.g., 0-citation papers)
- **Scale Multiplier**: Global size adjustment
- **Restore Sizes**: Button to restore sizes from CSV after reopening .blend files

### 4. Categorical Field Coloring
- Assigns field IDs to particles via angular_velocity channel
- Accessible in shader via Particle Info node → Angular Velocity → X component
- Auto-detects field columns: field_id, field_level_0/1/2, category, cluster
- Selectable hierarchy level (0=broad ~19 fields, 1=medium ~268, 2=fine ~3111)

---

## Compilation Instructions (macOS ARM64 / Apple Silicon)

### Prerequisites

```bash
# Install Homebrew Python 3.11 (matches Blender 4.5's Python)
brew install python@3.11

# Install Cython
/opt/homebrew/bin/pip3.11 install cython
```

### Compile the Cython Core Module

```bash
cd /path/to/molecular-plus/c_sources

# Run the ARM64 build script
/opt/homebrew/bin/python3.11 setup_arm64.py build_ext --inplace
```

This creates `molecular_core/` containing `core.cpython-311-darwin.so`.

### Verify Compilation

```bash
# Check the compiled library links correctly
otool -L molecular_core/core.cpython-311-darwin.so

# Should show libomp.dylib and system libraries
```

---

## Installation Instructions

### Option A: Automated Install Script

Create and run this script to install the addon:

```bash
#!/bin/bash
# install_molecular_plus.sh

ADDON_NAME="molecular_plus"
SOURCE_DIR="/path/to/molecular-plus"  # Change this to your molecular-plus location
BLENDER_ADDONS="$HOME/Library/Application Support/Blender/4.5/scripts/addons"
BLENDER_SITE_PACKAGES="/Applications/Blender 4.5.app/Contents/Resources/4.5/python/lib/python3.11/site-packages"

# Create addon directory
mkdir -p "$BLENDER_ADDONS/$ADDON_NAME"

# Copy Python files
cp "$SOURCE_DIR"/*.py "$BLENDER_ADDONS/$ADDON_NAME/"

# Copy compiled core module to Blender's site-packages
cp -r "$SOURCE_DIR/c_sources/molecular_core" "$BLENDER_SITE_PACKAGES/"

echo "Installation complete!"
echo "Enable 'Molecular Plus' in Blender: Edit > Preferences > Add-ons"
```

### Option B: Manual Installation

1. **Copy Python addon files:**
   ```bash
   mkdir -p ~/Library/Application\ Support/Blender/4.5/scripts/addons/molecular_plus/
   cp /path/to/molecular-plus/*.py ~/Library/Application\ Support/Blender/4.5/scripts/addons/molecular_plus/
   ```

2. **Copy compiled core module:**
   ```bash
   cp -r /path/to/molecular-plus/c_sources/molecular_core \
         "/Applications/Blender 4.5.app/Contents/Resources/4.5/python/lib/python3.11/site-packages/"
   ```

3. **Enable in Blender:**
   - Open Blender
   - Go to Edit → Preferences → Add-ons
   - Search for "Molecular"
   - Enable "Molecular Plus"

---

## Usage

### Basic Setup
1. Create an emitter object (plane, sphere, etc.)
2. Add a Particle System
3. In Physics tab, enable "Molecular Plus" checkbox
4. Configure simulation parameters
5. Click "Start Simulation"

### Using CSV Initial Positions
1. Enable "Molecular Plus" on particle system
2. Set "Initial CSV" path to your CSV file
3. CSV must have columns: `x,y,z` or `tsne_x,tsne_y,tsne_z`
4. Optional columns: `cited_by_count` (for sizes), `field_level_0` (for colors)

### Using Field Colors in Shader
1. In shader editor, add "Particle Info" node
2. Connect "Angular Velocity" → "Separate XYZ" → use "X" output
3. X contains the field ID (0, 1, 2, ... N)
4. Use ColorRamp or math nodes to map IDs to colors

### Restoring Sizes After Reopening
1. Open your saved .blend file
2. Select the emitter object
3. In Physics tab → Molecular Plus panel
4. Click "Restore Sizes from CSV"

---

## File Structure

```
molecular-plus/
├── __init__.py          # Addon registration
├── operators.py         # Blender operators (simulate, restore sizes, etc.)
├── properties.py        # Blender properties (UI settings)
├── simulate.py          # Python simulation logic, CSV loading
├── ui.py                # UI panel definitions
├── descriptions.py      # Tooltip descriptions
├── utils.py             # Utility functions
├── c_sources/
│   ├── setup_arm64.py   # macOS ARM64 build script
│   ├── init.pyx         # Cython initialization
│   ├── simulate.pyx     # Cython simulation core (Barnes-Hut gravity)
│   ├── structures.pyx   # Data structures (Particle, ParSys, Octree)
│   └── molecular_core/  # Compiled output directory
└── README.md            # This file
```

---

## Troubleshooting

### "No module named 'molecular_core'"
The compiled core module is not in Blender's Python path. Copy `molecular_core/` to Blender's site-packages directory.

### Particles don't move
- Ensure "Molecular Plus" is enabled (checkbox checked)
- Click "Start Simulation" button
- Check console for errors

### Sizes not loading from CSV
- Verify CSV has a scale column (cited_by_count, scale, size, mass, etc.)
- Check Min Scale is not too high
- Try "Restore Sizes from CSV" button

### Field colors all the same
- Verify CSV has a field column (field_level_0, field_id, category, etc.)
- Check shader is reading Angular Velocity X component
- Field IDs are integers starting from 0

---

## Credits

- Original Molecular addon: [pyroevil](https://github.com/Pyroevil/Blender-Molecular-Script)
- Blender 2.8+ compatibility: [PavelBlend](https://github.com/pablodp606) and [Scorpion81](https://github.com/scorpion81/Blender-Molecular-Script)
- Molecular Plus: [u3dreal](https://github.com/u3dreal/molecular-plus)
- Barnes-Hut gravity, CSV features: UCL Eye project

## License

GPL-3.0 (inherited from original Molecular addon)
