"""
Test script for Hero Tracker addon.
Run with: /Applications/Blender\ 4.5.app/Contents/MacOS/Blender --background --python test_addon.py
"""

import bpy
import sys
import math

def setup_test_scene():
    """Create a test scene with camera and particle system."""
    print("\n" + "="*60)
    print("HERO TRACKER ADDON TEST")
    print("="*60)

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Create a plane as particle emitter
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
    emitter = bpy.context.active_object
    emitter.name = "ParticleEmitter"

    # Add particle system
    bpy.ops.object.particle_system_add()
    psys = emitter.particle_systems[0]
    psys.name = "TestParticles"  # Named particle system
    psys_settings = psys.settings

    # Configure particle system
    psys_settings.count = 100
    psys_settings.emit_from = 'FACE'
    psys_settings.distribution = 'RAND'
    psys_settings.frame_start = 1
    psys_settings.frame_end = 1
    psys_settings.lifetime = 250
    psys_settings.physics_type = 'NO'  # No physics, static particles
    psys_settings.particle_size = 0.2
    psys_settings.size_random = 0.5  # Random sizes

    print(f"Created emitter with particle system: {psys.name}")

    # Create camera
    bpy.ops.object.camera_add(location=(0, -10, 5))
    camera = bpy.context.active_object
    camera.name = "TestCamera"

    # Point camera at origin
    camera.rotation_euler = (math.radians(60), 0, 0)

    # Set as active camera
    bpy.context.scene.camera = camera

    print(f"Created camera: {camera.name}")

    # Set frame range
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 10

    # Move to frame 1 to initialize particles
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()

    return emitter, psys, camera


def test_addon():
    """Test the Hero Tracker addon."""

    # Setup test scene FIRST (this resets Blender)
    print("\n1. Setting up test scene...")
    emitter, psys, camera = setup_test_scene()

    # Enable the addon AFTER scene reset
    print("\n2. Enabling Hero Tracker addon...")
    try:
        bpy.ops.preferences.addon_enable(module="hero_tracker")
        print("   [OK] Addon enabled")
    except Exception as e:
        print(f"   [FAIL] Could not enable addon: {e}")
        return False

    # Configure addon properties
    print("\n3. Configuring addon properties...")
    props = bpy.context.scene.hero_tracker
    props.particle_system_name = "TestParticles"
    props.camera = camera
    props.view_margin = 0.1  # 10% margin outside frame
    print(f"   Particle system: {props.particle_system_name}")
    print(f"   Camera: {props.camera.name}")
    print(f"   Margin: {props.view_margin}")

    # Test finding particle system
    print("\n4. Testing particle system lookup...")
    from hero_tracker import find_particle_system_by_name
    obj, idx = find_particle_system_by_name(bpy.context, "TestParticles")
    if obj is None:
        print("   [FAIL] Could not find particle system")
        return False
    print(f"   [OK] Found particle system on object: {obj.name}")

    # Test frustum check
    print("\n5. Testing camera frustum check...")
    from hero_tracker import is_point_in_camera_view
    from mathutils import Vector

    # Point at origin should be in view
    in_view, coords = is_point_in_camera_view(camera, Vector((0, 0, 0)), 0.0)
    print(f"   Origin in view: {in_view}, coords: {coords}")

    # Point behind camera should not be in view
    in_view_behind, _ = is_point_in_camera_view(camera, Vector((0, 20, 0)), 0.0)
    print(f"   Behind camera in view: {in_view_behind}")

    if not in_view:
        print("   [WARN] Origin not in camera view - camera may need adjustment")

    # Test finding most prominent particle
    print("\n6. Testing particle finding...")
    from hero_tracker import find_most_prominent_particle
    idx, loc, size = find_most_prominent_particle(
        bpy.context, obj, 0, camera, 0.1
    )
    print(f"   Most prominent particle: idx={idx}, loc={loc}, size={size}")

    if idx < 0:
        print("   [WARN] No particle found in view")
    else:
        print("   [OK] Found particle in view")

    # Run bake operator
    print("\n7. Running bake operator...")
    try:
        result = bpy.ops.herotracker.bake()
        print(f"   Operator result: {result}")
    except Exception as e:
        print(f"   [FAIL] Bake failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Check if HeroEmpty was created
    print("\n8. Checking results...")
    if "HeroEmpty" not in bpy.data.objects:
        print("   [FAIL] HeroEmpty not created")
        return False
    print("   [OK] HeroEmpty exists")

    hero = bpy.data.objects["HeroEmpty"]

    # Check animation data
    if hero.animation_data is None or hero.animation_data.action is None:
        print("   [WARN] HeroEmpty has no animation")
    else:
        action = hero.animation_data.action
        keyframe_count = len(action.fcurves[0].keyframe_points) if action.fcurves else 0
        print(f"   [OK] HeroEmpty has animation with {keyframe_count} keyframes")

    # Print hero empty position at frame 1
    bpy.context.scene.frame_set(1)
    print(f"   Frame 1 - Location: {hero.location}, Scale: {hero.scale}")

    print("\n" + "="*60)
    print("TEST COMPLETED SUCCESSFULLY")
    print("="*60)

    return True


if __name__ == "__main__":
    success = test_addon()
    sys.exit(0 if success else 1)
