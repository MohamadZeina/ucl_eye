"""
Test Hero Tracker v1.1 with custom properties and fade logic.
"""

import bpy
import sys
import math

def setup_test_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Create emitter
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    emitter = bpy.context.active_object
    emitter.name = "Emitter"

    # Add particle system
    bpy.ops.object.particle_system_add()
    psys = emitter.particle_systems[0]
    psys.name = "TestParticles"
    psys.settings.count = 100
    psys.settings.emit_from = 'FACE'
    psys.settings.frame_start = 1
    psys.settings.frame_end = 1
    psys.settings.lifetime = 500
    psys.settings.physics_type = 'NO'
    psys.settings.particle_size = 0.3
    psys.settings.size_random = 0.5

    # Create camera that moves
    bpy.ops.object.camera_add(location=(-10, -10, 8))
    camera = bpy.context.active_object
    camera.name = "Camera"

    # Add constraint to look at origin
    constraint = camera.constraints.new(type='TRACK_TO')
    constraint.target = emitter
    constraint.track_axis = 'TRACK_NEGATIVE_Z'
    constraint.up_axis = 'UP_Y'

    bpy.context.scene.camera = camera

    # Animate camera
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 50

    scene.frame_set(1)
    camera.location = (-10, -10, 8)
    camera.keyframe_insert(data_path="location", frame=1)

    scene.frame_set(25)
    camera.location = (0, -15, 5)
    camera.keyframe_insert(data_path="location", frame=25)

    scene.frame_set(50)
    camera.location = (10, -10, 8)
    camera.keyframe_insert(data_path="location", frame=50)

    scene.frame_set(1)
    bpy.context.view_layer.update()

    return emitter, psys, camera


def test_custom_properties():
    print("\n" + "="*60)
    print("HERO TRACKER v1.1 - CUSTOM PROPERTIES TEST")
    print("="*60)

    # Setup
    print("\n1. Setting up scene...")
    emitter, psys, camera = setup_test_scene()

    # Enable addon
    print("\n2. Enabling addon...")
    bpy.ops.preferences.addon_enable(module="hero_tracker")

    # Configure
    print("\n3. Configuring...")
    props = bpy.context.scene.hero_tracker
    props.particle_system_name = "TestParticles"
    props.camera = camera
    props.view_margin = 0.0
    props.fade_frames = 5
    print(f"   Fade frames: {props.fade_frames}")

    # Bake
    print("\n4. Baking...")
    result = bpy.ops.herotracker.bake()
    print(f"   Result: {result}")

    # Check results
    print("\n5. Checking custom properties...")

    hero = bpy.data.objects.get("HeroEmpty")
    if not hero:
        print("   [FAIL] HeroEmpty not found")
        return False

    # Check custom properties exist
    expected_props = ['particle_index', 'opacity', 'particle_distance',
                      'screen_x', 'screen_y', 'is_transition']

    for prop in expected_props:
        if prop in hero:
            print(f"   [OK] {prop} exists: {hero[prop]}")
        else:
            print(f"   [FAIL] {prop} missing")
            return False

    # Check animation data
    if not hero.animation_data or not hero.animation_data.action:
        print("   [FAIL] No animation data")
        return False

    fcurves = hero.animation_data.action.fcurves
    print(f"\n6. F-Curves found: {len(fcurves)}")

    for fc in fcurves:
        keyframes = len(fc.keyframe_points)
        print(f"   {fc.data_path}: {keyframes} keyframes")

    # Sample some frames
    print("\n7. Sampling frames...")
    print("   " + "-"*60)
    print(f"   {'Frame':<6} {'Index':<6} {'Opacity':<8} {'Distance':<10} {'Transition':<10}")
    print("   " + "-"*60)

    scene = bpy.context.scene
    transitions_found = 0
    prev_idx = None

    for frame in [1, 10, 20, 30, 40, 50]:
        scene.frame_set(frame)
        idx = int(hero['particle_index'])
        opacity = hero['opacity']
        dist = hero['particle_distance']
        is_trans = hero['is_transition']

        if prev_idx is not None and idx != prev_idx:
            transitions_found += 1
        prev_idx = idx

        print(f"   {frame:<6} {idx:<6} {opacity:<8.2f} {dist:<10.2f} {is_trans:<10}")

    print("   " + "-"*60)
    print(f"\n   Transitions detected during sampling: {transitions_found}")

    # Check opacity fading works
    print("\n8. Checking opacity fading...")

    # Find a transition and check opacity around it
    opacity_fcurve = None
    for fc in fcurves:
        if 'opacity' in fc.data_path:
            opacity_fcurve = fc
            break

    if opacity_fcurve:
        keyframes = [(kp.co[0], kp.co[1]) for kp in opacity_fcurve.keyframe_points]
        opacity_min = min(kf[1] for kf in keyframes)
        opacity_max = max(kf[1] for kf in keyframes)
        print(f"   Opacity range: {opacity_min:.2f} to {opacity_max:.2f}")

        if opacity_min < 0.5:
            print("   [OK] Opacity dips during transitions")
        else:
            print("   [WARN] Opacity never dips - may be no transitions")
    else:
        print("   [FAIL] No opacity fcurve found")

    print("\n" + "="*60)
    print("TEST COMPLETED")
    print("="*60)

    return True


if __name__ == "__main__":
    success = test_custom_properties()
    sys.exit(0 if success else 1)
