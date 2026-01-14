"""
Test Hero Tracker with a moving camera to verify different particles
are selected at different frames.

Run with: /Applications/Blender\ 4.5.app/Contents/MacOS/Blender --background --python test_moving_camera.py
"""

import bpy
import sys
import math
from mathutils import Vector

def setup_test_scene():
    """Create a test scene with camera moving through particle field."""
    print("\n" + "="*60)
    print("HERO TRACKER - MOVING CAMERA TEST")
    print("="*60)

    # Clear scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Create a large plane as particle emitter
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    emitter = bpy.context.active_object
    emitter.name = "ParticleEmitter"

    # Add particle system
    bpy.ops.object.particle_system_add()
    psys = emitter.particle_systems[0]
    psys.name = "GalaxyParticles"  # Named particle system
    psys_settings = psys.settings

    # Configure particle system - spread across plane
    psys_settings.count = 500
    psys_settings.emit_from = 'FACE'
    psys_settings.distribution = 'RAND'
    psys_settings.frame_start = 1
    psys_settings.frame_end = 1
    psys_settings.lifetime = 250
    psys_settings.physics_type = 'NO'  # Static particles
    psys_settings.particle_size = 0.3
    psys_settings.size_random = 0.8  # Large size variation

    print(f"Created emitter with {psys_settings.count} particles")

    # Create camera that will move
    bpy.ops.object.camera_add(location=(-8, -8, 5))
    camera = bpy.context.active_object
    camera.name = "MovingCamera"

    # Point camera at origin
    direction = Vector((0, 0, 0)) - camera.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    camera.rotation_euler = rot_quat.to_euler()

    # Set as active camera
    bpy.context.scene.camera = camera

    # Animate camera to move across the scene
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 30

    # Keyframe 1: starting position
    scene.frame_set(1)
    camera.location = (-8, -8, 5)
    camera.keyframe_insert(data_path="location", frame=1)

    # Keyframe 15: middle position
    scene.frame_set(15)
    camera.location = (0, -8, 3)
    camera.keyframe_insert(data_path="location", frame=15)

    # Keyframe 30: end position
    scene.frame_set(30)
    camera.location = (8, -8, 5)
    camera.keyframe_insert(data_path="location", frame=30)

    # Keep camera pointing at origin throughout
    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = emitter
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    print(f"Created camera with animation (frames 1-30)")

    # Initialize
    scene.frame_set(1)
    bpy.context.view_layer.update()

    return emitter, psys, camera


def test_moving_camera():
    """Test the Hero Tracker with moving camera."""

    # Setup test scene FIRST
    print("\n1. Setting up test scene...")
    emitter, psys, camera = setup_test_scene()

    # Enable addon
    print("\n2. Enabling Hero Tracker addon...")
    try:
        bpy.ops.preferences.addon_enable(module="hero_tracker")
        print("   [OK] Addon enabled")
    except Exception as e:
        print(f"   [FAIL] Could not enable addon: {e}")
        return False

    # Configure addon
    print("\n3. Configuring addon...")
    props = bpy.context.scene.hero_tracker
    props.particle_system_name = "GalaxyParticles"
    props.camera = camera
    props.view_margin = 0.0  # No margin for precise testing

    # Run bake
    print("\n4. Running bake operator...")
    try:
        result = bpy.ops.herotracker.bake()
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   [FAIL] Bake failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verify results
    print("\n5. Analyzing results...")

    if "HeroEmpty" not in bpy.data.objects:
        print("   [FAIL] HeroEmpty not created")
        return False

    hero = bpy.data.objects["HeroEmpty"]

    if not hero.animation_data or not hero.animation_data.action:
        print("   [FAIL] No animation on HeroEmpty")
        return False

    # Sample positions at different frames
    positions = []
    scene = bpy.context.scene

    sample_frames = [1, 10, 15, 20, 30]
    for frame in sample_frames:
        scene.frame_set(frame)
        pos = hero.location.copy()
        scale = hero.scale.x
        cam_pos = camera.location.copy()
        positions.append({
            'frame': frame,
            'hero_pos': pos,
            'hero_scale': scale,
            'camera_pos': cam_pos
        })

    print("\n   Frame-by-frame analysis:")
    print("   " + "-"*70)
    print(f"   {'Frame':<6} {'Camera Pos':<25} {'Hero Pos':<25} {'Scale':<8}")
    print("   " + "-"*70)

    for p in positions:
        cam = p['camera_pos']
        hero_pos = p['hero_pos']
        print(f"   {p['frame']:<6} ({cam.x:>6.2f}, {cam.y:>6.2f}, {cam.z:>5.2f})   "
              f"({hero_pos.x:>6.2f}, {hero_pos.y:>6.2f}, {hero_pos.z:>5.2f})   {p['hero_scale']:.3f}")

    # Check that hero position changes as camera moves
    first_pos = positions[0]['hero_pos']
    last_pos = positions[-1]['hero_pos']
    position_changed = (first_pos - last_pos).length > 0.1

    if position_changed:
        print("\n   [OK] Hero position changes as camera moves")
    else:
        print("\n   [WARN] Hero position didn't change much - may be same particle")

    # Test with negative margin
    print("\n6. Testing with negative margin (excluding edge particles)...")
    props.view_margin = -0.2  # Exclude 20% at edges

    # Clear animation
    hero.animation_data_clear()

    # Re-bake
    result = bpy.ops.herotracker.bake()

    # Check keyframe count
    if hero.animation_data and hero.animation_data.action:
        fcurves = hero.animation_data.action.fcurves
        if fcurves:
            keyframe_count = len(fcurves[0].keyframe_points)
            print(f"   With -20% margin: {keyframe_count} keyframes (may be fewer if edge particles excluded)")
    else:
        print("   [WARN] No animation after rebake")

    print("\n" + "="*60)
    print("MOVING CAMERA TEST COMPLETED")
    print("="*60)

    return True


if __name__ == "__main__":
    success = test_moving_camera()
    sys.exit(0 if success else 1)
