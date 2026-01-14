"""
Create a demo .blend file with Hero Tracker baked animation.
This file can be opened in Blender to visually inspect the results.

Run with: /Applications/Blender\ 4.5.app/Contents/MacOS/Blender --background --python create_demo_file.py
"""

import bpy
import sys
import math
from mathutils import Vector
import os

def setup_demo_scene():
    """Create a demo scene showing Hero Tracker in action."""
    print("\n" + "="*60)
    print("CREATING HERO TRACKER DEMO FILE")
    print("="*60)

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Create a plane as particle emitter
    bpy.ops.mesh.primitive_plane_add(size=15, location=(0, 0, 0))
    emitter = bpy.context.active_object
    emitter.name = "GalaxyEmitter"

    # Add particle system
    bpy.ops.object.particle_system_add()
    psys = emitter.particle_systems[0]
    psys.name = "GalaxyParticles"
    psys_settings = psys.settings

    # Configure particle system
    psys_settings.count = 200
    psys_settings.emit_from = 'FACE'
    psys_settings.distribution = 'RAND'
    psys_settings.frame_start = 1
    psys_settings.frame_end = 1
    psys_settings.lifetime = 500
    psys_settings.physics_type = 'NO'
    psys_settings.particle_size = 0.25
    psys_settings.size_random = 0.6

    # Use icosphere for particle rendering
    psys_settings.render_type = 'OBJECT'

    # Create a small sphere for particle instances
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1, subdivisions=2, location=(100, 100, 100))
    particle_obj = bpy.context.active_object
    particle_obj.name = "ParticleSphere"

    # Create material for particles
    mat = bpy.data.materials.new(name="ParticleMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.8, 0.6, 0.2, 1)  # Gold
        bsdf.inputs["Roughness"].default_value = 0.3
    particle_obj.data.materials.append(mat)

    psys_settings.instance_object = particle_obj

    print(f"Created particle system with {psys_settings.count} particles")

    # Create camera
    bpy.ops.object.camera_add(location=(-10, -10, 8))
    camera = bpy.context.active_object
    camera.name = "TrackingCamera"

    # Add track-to constraint to look at origin
    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = emitter
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    bpy.context.scene.camera = camera

    # Animate camera in a circle around the particles
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 100

    # Create circular path
    radius = 12
    height = 6

    keyframes = [1, 25, 50, 75, 100]
    angles = [0, 90, 180, 270, 360]

    for frame, angle in zip(keyframes, angles):
        scene.frame_set(frame)
        rad = math.radians(angle)
        camera.location = (
            radius * math.cos(rad),
            radius * math.sin(rad),
            height
        )
        camera.keyframe_insert(data_path="location", frame=frame)

    print("Created camera with circular orbit animation")

    # Add a light
    bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.data.energy = 3

    # Initialize
    scene.frame_set(1)
    bpy.context.view_layer.update()

    return emitter, psys, camera


def main():
    # Setup scene
    print("\n1. Setting up demo scene...")
    emitter, psys, camera = setup_demo_scene()

    # Enable addon
    print("\n2. Enabling Hero Tracker addon...")
    bpy.ops.preferences.addon_enable(module="hero_tracker")

    # Configure
    print("\n3. Configuring Hero Tracker...")
    props = bpy.context.scene.hero_tracker
    props.particle_system_name = "GalaxyParticles"
    props.camera = camera
    props.view_margin = 0.05  # 5% margin

    # Bake
    print("\n4. Baking hero track...")
    result = bpy.ops.herotracker.bake()
    print(f"   Bake result: {result}")

    # Customize the HeroEmpty for visibility
    if "HeroEmpty" in bpy.data.objects:
        hero = bpy.data.objects["HeroEmpty"]
        hero.empty_display_type = 'SPHERE'
        hero.empty_display_size = 1.0
        hero.show_in_front = True  # Always visible
        print("   Configured HeroEmpty for visibility")

    # Save file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "hero_tracker_demo.blend")

    print(f"\n5. Saving to: {output_path}")
    bpy.ops.wm.save_as_mainfile(filepath=output_path)

    print("\n" + "="*60)
    print("DEMO FILE CREATED SUCCESSFULLY")
    print(f"Open in Blender: {output_path}")
    print("Press Space to play animation and watch HeroEmpty track particles")
    print("="*60)


if __name__ == "__main__":
    main()
