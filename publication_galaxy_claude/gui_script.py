"""
SET PARTICLE POSITIONS FROM CSV - Frame Handler Approach

Uses a frame_change handler to set particle positions every frame.
This is how Molecular Plus works - modify particles during simulation.

WORKFLOW:
1. Run this script (registers the frame handler)
2. Play animation - particles will move to CSV positions
"""

import bpy
import csv

CSV_PATH = "/Users/mo/github/ucl_eye/publication_galaxy_claude/particles.csv"

# Global storage for coordinates and scale multipliers
_particle_data = []  # List of (x, y, z, scale_multiplier)
_handler_registered = False

def load_csv():
    """Load coordinates and scale multipliers from CSV file"""
    global _particle_data
    _particle_data = []
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            x, y, z = float(row['x']), float(row['y']), float(row['z'])
            scale = float(row.get('scale', 1.0))  # Default to 1.0 if no scale column
            _particle_data.append((x, y, z, scale))
    print(f"Loaded {len(_particle_data)} particles from CSV (with scale multipliers)")

def set_particle_positions(scene, depsgraph):
    """Frame change handler - sets particle positions and sizes every frame"""
    global _particle_data

    if not _particle_data:
        return

    # Find objects with particle systems
    for obj in scene.objects:
        if not obj.particle_systems:
            continue

        # Get evaluated object and original for base size
        obj_eval = obj.evaluated_get(depsgraph)

        for ps_idx, ps_eval in enumerate(obj_eval.particle_systems):
            if len(ps_eval.particles) == 0:
                continue

            # Get base size from GUI settings
            ps_original = obj.particle_systems[ps_idx]
            base_size = ps_original.settings.particle_size

            n_particles = min(len(_particle_data), len(ps_eval.particles))

            # Set positions and sizes for each particle
            for i in range(n_particles):
                x, y, z, scale_mult = _particle_data[i]
                ps_eval.particles[i].location = (x, y, z)
                ps_eval.particles[i].velocity = (0, 0, 0)

                # Size = base_size (from GUI) * scale_multiplier (from CSV)
                ps_eval.particles[i].size = base_size * scale_mult

def register_handler():
    """Register the frame change handler"""
    global _handler_registered

    # Remove existing handler if present
    if set_particle_positions in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(set_particle_positions)

    # Add handler
    bpy.app.handlers.frame_change_post.append(set_particle_positions)
    _handler_registered = True
    print("✓ Frame handler registered")

def unregister_handler():
    """Remove the frame change handler"""
    global _handler_registered

    if set_particle_positions in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(set_particle_positions)
    _handler_registered = False
    print("✓ Frame handler removed")

def main():
    """Main function - load CSV and register frame handler"""
    print("\n" + "="*80)
    print("PARTICLE POSITION CONTROLLER - Frame Handler")
    print("="*80)

    # Load CSV coordinates
    load_csv()

    # Register frame change handler
    register_handler()

    # Test by advancing one frame
    current = bpy.context.scene.frame_current
    bpy.context.scene.frame_set(current + 1)

    print(f"\n✓ Setup complete!")
    print(f"  Particles will be positioned from CSV on every frame change.")
    print(f"  Play animation to see effect.")
    print(f"\n  To disable: run unregister_handler()")
    print("="*80)

if __name__ == "__main__":
    main()
