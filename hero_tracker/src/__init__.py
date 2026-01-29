"""
Hero Tracker - Blender Addon

Finds the most prominent particle in camera view and tracks it with an empty.
For each frame, identifies which particle from a named particle system is
closest to the camera while being within the camera's view frustum.

Supports dual-camera tracking (forward and backward) for seamless loop rendering.
When both cameras are set, tracks are baked simultaneously for optimal performance.

Custom properties baked on HeroEmpty_fw / HeroEmpty_bw:
- particle_index: Which particle is currently tracked
- opacity: Fades out/in during transitions (for text display)
- particle_distance: Distance from camera to particle
- screen_x, screen_y: Normalized screen coordinates (0-1)
- is_transition: 1 if particle changed this frame, 0 otherwise

Optional Text Display:
- Enable "Text Display" in the panel and provide a CSV file path
- CSV should have columns: cleaned_title, decoded_abstract
- HeroText_fw and HeroText_bw text objects will be created and updated each frame
- Text shows the title and abstract of the currently tracked particle

Usage:
1. Name your particle system (e.g., "GalaxyParticles")
2. Open the N-panel > Hero Tracker tab
3. Enter the particle system name
4. Select your camera(s) - forward required, backward optional
5. (Optional) Enable Text Display and select CSV file
6. Click "Bake Hero Track"
7. Empties will be keyframed to follow the most prominent particle for each camera
"""

bl_info = {
    "name": "Hero Tracker",
    "author": "UCL Eye Project",
    "version": (3, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Hero Tracker",
    "description": "Track the most prominent particle in camera view with an empty",
    "category": "Animation",
}

import bpy
import array
import math
import csv
import random
import time
from mathutils import Vector
from bpy.props import StringProperty, FloatProperty, IntProperty, PointerProperty, EnumProperty, BoolProperty
from bpy.types import Panel, Operator, PropertyGroup
from bpy_extras.object_utils import world_to_camera_view


# =============================================================================
# TEXT DISPLAY - Global state for frame handler
# =============================================================================

# Dictionary mapping particle_index -> {"title": str, "abstract": str}
_paper_data = {}

# Track if our handler is registered
_text_handler_registered = False


# =============================================================================
# CORE LOGIC
# =============================================================================

def find_particle_system_by_name(context, psys_name):
    """
    Search all objects for a particle system with the given name.
    Returns (object, particle_system_index) or (None, -1) if not found.
    """
    for obj in bpy.data.objects:
        for i, psys in enumerate(obj.particle_systems):
            if psys.name == psys_name:
                return obj, i
    return None, -1


def is_point_in_camera_view(camera, point, margin=0.0):
    """
    Check if a 3D point is within the camera's view frustum.

    Args:
        camera: Camera object
        point: Vector - 3D world position
        margin: Float - margin as fraction of frame
                Positive = include points slightly outside frame
                Negative = exclude points near edges

    Returns:
        (in_view: bool, screen_coords: Vector or None, distance: float)
    """
    scene = bpy.context.scene

    # Get camera matrix
    cam_matrix = camera.matrix_world.normalized()
    cam_matrix_inv = cam_matrix.inverted()

    # Transform point to camera space
    point_cam = cam_matrix_inv @ point

    # Calculate distance
    distance = (point - camera.matrix_world.translation).length

    # Check if point is behind camera (negative Z in camera space means in front)
    if point_cam.z >= 0:
        return False, None, distance

    # Get camera data
    cam_data = camera.data

    # Calculate projection
    render = scene.render
    aspect = render.resolution_x / render.resolution_y

    if cam_data.type == 'PERSP':
        # Perspective projection
        if cam_data.sensor_fit == 'HORIZONTAL' or \
           (cam_data.sensor_fit == 'AUTO' and aspect >= 1):
            fov = 2 * math.atan(cam_data.sensor_width / (2 * cam_data.lens))
            fov_x = fov
            fov_y = 2 * math.atan(math.tan(fov / 2) / aspect)
        else:
            fov = 2 * math.atan(cam_data.sensor_height / (2 * cam_data.lens))
            fov_y = fov
            fov_x = 2 * math.atan(math.tan(fov / 2) * aspect)

        depth = -point_cam.z
        ndc_x = point_cam.x / (depth * math.tan(fov_x / 2))
        ndc_y = point_cam.y / (depth * math.tan(fov_y / 2))

    elif cam_data.type == 'ORTHO':
        scale = cam_data.ortho_scale
        ndc_x = point_cam.x / (scale / 2)
        ndc_y = point_cam.y / (scale / 2) * aspect
    else:
        return True, Vector((0.5, 0.5)), distance

    # NDC is in range [-1, 1], convert to [0, 1]
    screen_x = (ndc_x + 1) / 2
    screen_y = (ndc_y + 1) / 2

    # Apply margin
    lower = 0.0 - margin
    upper = 1.0 + margin

    in_view = (lower <= screen_x <= upper) and (lower <= screen_y <= upper)

    return in_view, Vector((screen_x, screen_y)), distance


def get_screen_radius(scene, camera, center, world_radius):
    """
    Get screen-space radius for a sphere.

    Args:
        scene: Blender scene
        camera: Camera object
        center: Vector - 3D world position of sphere center
        world_radius: Float - radius of sphere in world units

    Returns:
        (screen_radius, center_screen) where screen_radius is in normalized coords (0-1)
    """
    # Get camera's right vector (perpendicular to view)
    cam_matrix = camera.matrix_world
    cam_right = cam_matrix.to_3x3() @ Vector((1, 0, 0))

    # Project center and a point offset by radius
    center_screen = world_to_camera_view(scene, camera, center)
    edge_point = center + cam_right * world_radius
    edge_screen = world_to_camera_view(scene, camera, edge_point)

    # Screen radius is the distance between them (in X-Y plane)
    screen_radius = (Vector(edge_screen[:2]) - Vector(center_screen[:2])).length
    return screen_radius, center_screen


def find_most_prominent_particle(context, obj, psys_index, camera, margin, mode='CLOSEST'):
    """
    Find the most prominent particle within the camera's view frustum.

    Args:
        context: Blender context
        obj: Object containing the particle system
        psys_index: Index of the particle system
        camera: Camera object
        margin: View margin (fraction of frame)
        mode: Selection mode
            'CLOSEST' - Find particle closest to camera
            'LARGEST_ON_SCREEN' - Find particle with largest angular size (size/distance)

    Returns:
        dict with keys: index, location, size, distance, screen_x, screen_y, angular_size
        or None if no particle found
    """
    depsgraph = context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)

    if psys_index >= len(obj_eval.particle_systems):
        return None

    psys_eval = obj_eval.particle_systems[psys_index]
    n_particles = len(psys_eval.particles)

    if n_particles == 0:
        return None

    # Get camera position
    cam_loc = camera.matrix_world.translation

    # Get all particle locations using foreach_get (fast bulk access)
    par_loc = array.array('f', [0.0]) * (n_particles * 3)
    par_size = array.array('f', [0.0]) * n_particles

    psys_eval.particles.foreach_get('location', par_loc)
    psys_eval.particles.foreach_get('size', par_size)

    # Find best particle based on mode
    best = None

    if mode == 'CLOSEST':
        best_score = float('inf')  # Lower distance is better
    else:  # LARGEST_ON_SCREEN
        best_score = 0.0  # Higher angular size is better

    for i in range(n_particles):
        px = par_loc[i * 3]
        py = par_loc[i * 3 + 1]
        pz = par_loc[i * 3 + 2]
        p_loc = Vector((px, py, pz))

        # Check if in camera view
        in_view, screen_coords, distance = is_point_in_camera_view(camera, p_loc, margin)
        if not in_view:
            continue

        # Calculate distance to camera
        dist_sq = (px - cam_loc.x)**2 + (py - cam_loc.y)**2 + (pz - cam_loc.z)**2
        dist = math.sqrt(dist_sq) if dist_sq > 0 else 0.0001

        # Calculate angular size (apparent size on screen)
        # This is proportional to physical_size / distance
        angular_size = par_size[i] / dist if dist > 0 else 0

        # Determine if this particle is better based on mode
        if mode == 'CLOSEST':
            score = dist_sq
            is_better = score < best_score
        else:  # LARGEST_ON_SCREEN
            score = angular_size
            is_better = score > best_score

        if is_better:
            best_score = score
            best = {
                'index': i,
                'location': p_loc,
                'size': par_size[i],
                'distance': distance,
                'screen_x': screen_coords.x,
                'screen_y': screen_coords.y,
                'angular_size': angular_size,
            }

    return best


def get_or_create_hero_empty(context, suffix):
    """
    Get or create the HeroEmpty object with given suffix.

    Args:
        context: Blender context
        suffix: String suffix like "_fw" or "_bw"

    Returns the empty object.
    """
    hero_name = f"HeroEmpty{suffix}"

    if hero_name in bpy.data.objects:
        return bpy.data.objects[hero_name]

    # Create new empty
    empty = bpy.data.objects.new(hero_name, None)
    empty.empty_display_type = 'SPHERE'
    empty.empty_display_size = 1.0

    # Link to scene
    context.collection.objects.link(empty)

    return empty


def initialize_custom_properties(hero_empty):
    """Initialize custom properties with default values and configure UI."""
    # Define properties with their defaults and UI settings
    # Format: (default_value, min, max, soft_min, soft_max, step, precision)
    float_props = {
        'opacity': (1.0, 0.0, 1.0, 0.0, 1.0, 0.01, 3),
        'particle_distance': (0.0, 0.0, 10000.0, 0.0, 100.0, 0.1, 2),
        'screen_x': (0.5, 0.0, 1.0, 0.0, 1.0, 0.01, 3),
        'screen_y': (0.5, 0.0, 1.0, 0.0, 1.0, 0.01, 3),
    }

    int_props = {
        'particle_index': (0, -1, 1000000),
        'is_transition': (0, 0, 1),
    }

    # Initialize float properties
    for prop_name, (default, min_val, max_val, soft_min, soft_max, step, precision) in float_props.items():
        if prop_name not in hero_empty:
            hero_empty[prop_name] = default

        id_props = hero_empty.id_properties_ui(prop_name)
        id_props.update(
            min=min_val,
            max=max_val,
            soft_min=soft_min,
            soft_max=soft_max,
            step=step,
            precision=precision
        )

    # Initialize int properties
    for prop_name, (default, min_val, max_val) in int_props.items():
        if prop_name not in hero_empty:
            hero_empty[prop_name] = default

        id_props = hero_empty.id_properties_ui(prop_name)
        id_props.update(min=min_val, max=max_val)


def keyframe_custom_property(hero_empty, prop_name, value, frame):
    """Set and keyframe a custom property."""
    hero_empty[prop_name] = value
    hero_empty.keyframe_insert(data_path=f'["{prop_name}"]', frame=frame)


# =============================================================================
# TEXT DISPLAY FUNCTIONS
# =============================================================================

def load_paper_csv(csv_path):
    """
    Load paper data from CSV file.

    Expects columns: cleaned_title, decoded_abstract
    Returns dict mapping row index -> {"title": str, "abstract": str}
    """
    global _paper_data
    _paper_data = {}

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                title = row.get('cleaned_title', '')
                abstract = row.get('decoded_abstract', '')
                _paper_data[idx] = {
                    'title': title,
                    'abstract': abstract
                }
        return len(_paper_data)
    except Exception as e:
        print(f"Hero Tracker: Error loading CSV: {e}")
        return 0


def get_or_create_hero_text(context, suffix):
    """
    Get or create the HeroText text object with given suffix.

    Args:
        context: Blender context
        suffix: String suffix like "_fw" or "_bw"

    Returns the text object.
    """
    text_name = f"HeroText{suffix}"

    if text_name in bpy.data.objects:
        return bpy.data.objects[text_name]

    # Create new text object
    text_data = bpy.data.curves.new(name=text_name, type='FONT')
    text_data.body = "Waiting for hero..."
    text_data.align_x = 'LEFT'
    text_data.align_y = 'TOP'

    text_obj = bpy.data.objects.new(text_name, text_data)

    # Link to scene
    context.collection.objects.link(text_obj)

    return text_obj


def _update_text_for_hero(hero, text_obj):
    """Helper to update a single text object from a hero empty."""
    global _paper_data

    if not hero or not text_obj:
        return

    if "particle_index" not in hero:
        return

    idx = int(hero["particle_index"])
    paper = _paper_data.get(idx)

    if paper:
        title = paper.get('title', '')
        abstract = paper.get('abstract', '')
        combined = f"{title} - {abstract}"
        combined = combined.replace('\n', ' ').replace('\r', ' ')
        while '  ' in combined:
            combined = combined.replace('  ', ' ')
        text_obj.data.body = combined
    else:
        text_obj.data.body = f"No paper data for index {idx}"


def update_hero_text(scene, depsgraph):
    """
    Frame change handler - updates HeroText_fw and HeroText_bw based on particle_index.
    """
    global _paper_data

    if not _paper_data:
        return

    # Update forward text
    hero_fw = bpy.data.objects.get("HeroEmpty_fw")
    text_fw = bpy.data.objects.get("HeroText_fw")
    _update_text_for_hero(hero_fw, text_fw)

    # Update backward text
    hero_bw = bpy.data.objects.get("HeroEmpty_bw")
    text_bw = bpy.data.objects.get("HeroText_bw")
    _update_text_for_hero(hero_bw, text_bw)


def register_text_handler():
    """Register the frame change handler for text updates."""
    global _text_handler_registered

    # Remove existing handler if present
    if update_hero_text in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(update_hero_text)

    bpy.app.handlers.frame_change_post.append(update_hero_text)
    _text_handler_registered = True
    print("Hero Tracker: Text update handler registered")


def unregister_text_handler():
    """Remove the frame change handler for text updates."""
    global _text_handler_registered

    if update_hero_text in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(update_hero_text)
    _text_handler_registered = False
    print("Hero Tracker: Text update handler removed")


# =============================================================================
# OPERATORS
# =============================================================================

class HEROTRACKER_OT_bake(Operator):
    """Bake hero tracking for all frames in the timeline"""
    bl_idname = "herotracker.bake"
    bl_label = "Bake Hero Track"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.hero_tracker

        # Validate inputs
        if not props.particle_system_name:
            self.report({'ERROR'}, "Please enter a particle system name")
            return {'CANCELLED'}

        if not props.camera_fw and not props.camera_bw:
            self.report({'ERROR'}, "Please select at least one camera")
            return {'CANCELLED'}

        # Find particle system
        obj, psys_idx = find_particle_system_by_name(context, props.particle_system_name)
        if obj is None:
            self.report({'ERROR'}, f"Particle system '{props.particle_system_name}' not found")
            return {'CANCELLED'}

        # Determine which cameras to use
        cameras = []
        if props.camera_fw:
            cameras.append(('_fw', props.camera_fw))
        if props.camera_bw:
            cameras.append(('_bw', props.camera_bw))

        view_margin = props.view_margin
        switch_margin = props.switch_margin
        selection_mode = props.selection_mode
        lookahead_frames = props.lookahead_frames
        fade_frames = props.fade_frames

        # Unregister text handler during bake - it fires on every frame_set()
        # and writes to text objects, causing massive slowdown on subsequent bakes
        text_handler_was_active = update_hero_text in bpy.app.handlers.frame_change_post
        if text_handler_was_active:
            bpy.app.handlers.frame_change_post.remove(update_hero_text)

        # Get or create hero empties and clear animation
        hero_empties = {}
        for suffix, camera in cameras:
            hero_empty = get_or_create_hero_empty(context, suffix)
            if hero_empty.animation_data:
                hero_empty.animation_data_clear()
            initialize_custom_properties(hero_empty)
            hero_empties[suffix] = hero_empty

        # Get frame range
        frame_start = scene.frame_start
        frame_end = scene.frame_end
        total_frames = frame_end - frame_start + 1

        # Build list of frames to evaluate based on frame_step
        frame_step = props.frame_step
        if frame_step == 1:
            eval_frames = list(range(frame_start, frame_end + 1))
        else:
            eval_frames = list(range(frame_start, frame_end + 1, frame_step))
            # Always include the last frame for clean loop closure
            if frame_end not in eval_frames:
                eval_frames.append(frame_end)
        total_eval_frames = len(eval_frames)

        # Store current frame to restore later
        original_frame = scene.frame_current

        # Helper to get particle data by index for a specific camera
        def get_particle_by_index_for_camera(particle_index, camera):
            """Get particle data for a specific particle index at current frame."""
            depsgraph = context.evaluated_depsgraph_get()
            obj_eval = obj.evaluated_get(depsgraph)

            if psys_idx >= len(obj_eval.particle_systems):
                return None

            psys_eval = obj_eval.particle_systems[psys_idx]
            n_particles = len(psys_eval.particles)

            if particle_index < 0 or particle_index >= n_particles:
                return None

            particle = psys_eval.particles[particle_index]
            p_loc = Vector(particle.location)
            p_size = particle.size

            cam_loc = camera.matrix_world.translation
            dist = (p_loc - cam_loc).length

            in_view, screen_coords, distance = is_point_in_camera_view(camera, p_loc, 0.5)

            if screen_coords is None:
                return None

            return {
                'index': particle_index,
                'location': p_loc,
                'size': p_size,
                'distance': dist,
                'screen_x': screen_coords.x,
                'screen_y': screen_coords.y,
            }

        def is_hero_out_of_frame(particle_data, camera, margin):
            """Check if hero particle is out of frame considering margin."""
            if particle_data is None:
                return True

            screen_radius, _ = get_screen_radius(
                scene, camera, particle_data['location'], particle_data['size']
            )

            sx = particle_data['screen_x']
            sy = particle_data['screen_y']

            lower = 0.0 - margin
            upper = 1.0 + margin

            out_left = sx + screen_radius < lower
            out_right = sx - screen_radius > upper
            out_bottom = sy + screen_radius < lower
            out_top = sy - screen_radius > upper

            return out_left or out_right or out_bottom or out_top

        # Initialize tracking state for each camera
        track_state = {}
        for suffix, camera in cameras:
            track_state[suffix] = {
                'camera': camera,
                'current_hero_idx': None,
                'frame_heroes': [],  # (frame, idx, data)
                'transition_frames': [],
            }

        def format_duration(seconds):
            """Format seconds into human-readable duration (s/m/h)."""
            if seconds < 1:
                return "<1s"
            elif seconds < 60:
                return f"{seconds:.0f}s"
            elif seconds < 3600:
                mins = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{mins}m {secs}s" if secs > 0 else f"{mins}m"
            else:
                hours = int(seconds // 3600)
                mins = int((seconds % 3600) // 60)
                if mins > 0:
                    return f"{hours}h {mins}m"
                else:
                    return f"{hours}h"

        if frame_step == 1:
            print(f"Hero Tracker: Baking {total_frames} frames for {len(cameras)} camera(s)...")
        else:
            print(f"Hero Tracker: Baking {total_eval_frames}/{total_frames} frames (step={frame_step}, ~{frame_step}x faster) for {len(cameras)} camera(s)...")
        bake_start_time = time.time()

        # =====================================================================
        # PASS 1: Evaluate selected frames, process all cameras per frame
        # =====================================================================
        for i, frame in enumerate(eval_frames):
            if i == 0 or (i + 1) % 10 == 0 or i == total_eval_frames - 1:
                pct = 100 * (i + 1) / total_eval_frames
                elapsed = time.time() - bake_start_time
                if i > 0:
                    time_per_frame = elapsed / (i + 1)
                    eta = time_per_frame * (total_eval_frames - i - 1)
                    eta_str = f", ETA: {format_duration(eta)}"
                    # Theoretical projections for 1k/10k/100k timeline frames
                    # With step=2, 100k timeline = ~50k evaluated, so divide by frame_step
                    proj_1k = format_duration(time_per_frame * 1000 / frame_step)
                    proj_10k = format_duration(time_per_frame * 10000 / frame_step)
                    proj_100k = format_duration(time_per_frame * 100000 / frame_step)
                    proj_str = f" | 1k: {proj_1k}, 10k: {proj_10k}, 100k: {proj_100k}"
                else:
                    eta_str = ""
                    proj_str = ""
                print(f"  Pass 1/2: Frame {frame} ({i + 1}/{total_eval_frames}) - {pct:.1f}%{eta_str}{proj_str}")

            scene.frame_set(frame)

            # Process each camera at this frame
            for suffix, camera in cameras:
                state = track_state[suffix]
                current_hero_idx = state['current_hero_idx']

                # Check if current hero is still valid
                need_new_hero = False
                current_hero_data = None

                if current_hero_idx is not None:
                    current_hero_data = get_particle_by_index_for_camera(current_hero_idx, camera)
                    if is_hero_out_of_frame(current_hero_data, camera, switch_margin):
                        need_new_hero = True
                else:
                    need_new_hero = True

                if need_new_hero:
                    # Find best new hero
                    if lookahead_frames > 0:
                        future_frame = min(frame + lookahead_frames, frame_end)
                        scene.frame_set(future_frame)
                        new_hero_future = find_most_prominent_particle(
                            context, obj, psys_idx, camera, view_margin, selection_mode
                        )
                        scene.frame_set(frame)

                        if new_hero_future is not None:
                            new_hero = get_particle_by_index_for_camera(new_hero_future['index'], camera)
                        else:
                            new_hero = find_most_prominent_particle(
                                context, obj, psys_idx, camera, view_margin, selection_mode
                            )
                    else:
                        new_hero = find_most_prominent_particle(
                            context, obj, psys_idx, camera, view_margin, selection_mode
                        )

                    if new_hero is not None:
                        if current_hero_idx is not None and new_hero['index'] != current_hero_idx:
                            state['transition_frames'].append(frame)
                        state['current_hero_idx'] = new_hero['index']
                        state['frame_heroes'].append((frame, new_hero['index'], new_hero))
                    else:
                        state['frame_heroes'].append((frame, None, None))
                        state['current_hero_idx'] = None
                else:
                    state['frame_heroes'].append((frame, current_hero_idx, current_hero_data))

        pass1_time = time.time() - bake_start_time
        print(f"  Pass 1 complete in {pass1_time:.1f}s")

        # =====================================================================
        # PASS 2: Keyframe all empties from cached data
        # =====================================================================
        pass2_start_time = time.time()
        print(f"  Pass 2/2: Baking keyframes...")

        results = {}
        for suffix, camera in cameras:
            state = track_state[suffix]
            hero_empty = hero_empties[suffix]
            frame_heroes = state['frame_heroes']
            transition_frames = state['transition_frames']

            frames_with_particle = 0
            frames_without_particle = 0

            for j, (frame, hero_idx, hero_data) in enumerate(frame_heroes):
                if hero_data is not None:
                    hero_empty.location = hero_data['location']
                    hero_empty.keyframe_insert(data_path="location", frame=frame)

                    scale_val = max(hero_data['size'], 0.01)
                    hero_empty.scale = (scale_val, scale_val, scale_val)
                    hero_empty.keyframe_insert(data_path="scale", frame=frame)

                    keyframe_custom_property(hero_empty, 'particle_index', hero_data['index'], frame)
                    keyframe_custom_property(hero_empty, 'particle_distance', hero_data['distance'], frame)
                    keyframe_custom_property(hero_empty, 'screen_x', hero_data['screen_x'], frame)
                    keyframe_custom_property(hero_empty, 'screen_y', hero_data['screen_y'], frame)

                    is_trans = 1 if frame in transition_frames else 0
                    keyframe_custom_property(hero_empty, 'is_transition', is_trans, frame)

                    frames_with_particle += 1
                else:
                    frames_without_particle += 1

            # Keyframe opacity at transition points
            opacity_keyframes = set()
            if frames_with_particle > 0:
                opacity_keyframes.add((frame_start, 1.0))
                opacity_keyframes.add((frame_end, 1.0))

            for t_frame in transition_frames:
                opacity_keyframes.add((t_frame, 0.0))
                fade_out_start = t_frame - fade_frames
                if fade_out_start >= frame_start:
                    opacity_keyframes.add((fade_out_start, 1.0))
                fade_in_end = t_frame + fade_frames
                if fade_in_end <= frame_end:
                    opacity_keyframes.add((fade_in_end, 1.0))

            for frame, opacity in sorted(opacity_keyframes):
                keyframe_custom_property(hero_empty, 'opacity', opacity, frame)

            # Set interpolation modes
            if hero_empty.animation_data and hero_empty.animation_data.action:
                for fcurve in hero_empty.animation_data.action.fcurves:
                    if 'opacity' in fcurve.data_path:
                        for keyframe in fcurve.keyframe_points:
                            keyframe.interpolation = 'LINEAR'
                    elif 'particle_index' in fcurve.data_path or 'is_transition' in fcurve.data_path:
                        for keyframe in fcurve.keyframe_points:
                            keyframe.interpolation = 'CONSTANT'

            results[suffix] = {
                'frames_with_particle': frames_with_particle,
                'transitions': len(transition_frames),
            }

        # Restore original frame
        scene.frame_set(original_frame)

        pass2_time = time.time() - pass2_start_time
        total_time = time.time() - bake_start_time
        print(f"  Pass 2 complete in {pass2_time:.1f}s")

        # Build results summary
        results_str = ", ".join([f"{s}: {r['transitions']} trans" for s, r in results.items()])
        if frame_step == 1:
            print(f"Hero Tracker: Bake complete in {total_time:.1f}s. {results_str}")
        else:
            print(f"Hero Tracker: Bake complete in {total_time:.1f}s ({total_eval_frames}/{total_frames} frames, step={frame_step}). {results_str}")

        # Set up text display if enabled
        text_info = ""
        if props.enable_text_display and props.csv_file_path:
            num_papers = load_paper_csv(props.csv_file_path)
            if num_papers > 0:
                for suffix, camera in cameras:
                    get_or_create_hero_text(context, suffix)
                register_text_handler()
                update_hero_text(scene, context.evaluated_depsgraph_get())
                text_info = f" Text: {num_papers} papers."
            else:
                self.report({'WARNING'}, f"Could not load CSV: {props.csv_file_path}")

        # Report results
        mode_name = "closest" if selection_mode == 'CLOSEST' else "largest on screen"
        cam_info = f"{len(cameras)} cam" if len(cameras) > 1 else "1 cam"
        total_trans = sum(r['transitions'] for r in results.values())
        if frame_step == 1:
            frame_info = f"{total_frames}f"
        else:
            frame_info = f"{total_eval_frames}/{total_frames}f (step={frame_step})"
        self.report(
            {'INFO'},
            f"Baked {frame_info} x {cam_info} ({mode_name}). {total_trans} transitions.{text_info}"
        )

        return {'FINISHED'}


class HEROTRACKER_OT_clear(Operator):
    """Clear hero empty animation and text display"""
    bl_idname = "herotracker.clear"
    bl_label = "Clear Animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global _paper_data
        cleared_items = []

        # Clear fw, bw, and legacy (no suffix) empties
        for suffix in ['_fw', '_bw', '']:
            hero_name = f"HeroEmpty{suffix}" if suffix else "HeroEmpty"
            if hero_name in bpy.data.objects:
                hero = bpy.data.objects[hero_name]
                if hero.animation_data:
                    hero.animation_data_clear()
                    cleared_items.append(hero_name)

        # Unregister text handler
        if update_hero_text in bpy.app.handlers.frame_change_post:
            unregister_text_handler()
            cleared_items.append("text handler")

        # Clear paper data
        if _paper_data:
            _paper_data = {}
            cleared_items.append("paper data")

        if cleared_items:
            self.report({'INFO'}, f"Cleared: {', '.join(cleared_items)}")
        else:
            self.report({'INFO'}, "Nothing to clear")

        return {'FINISHED'}


class HEROTRACKER_OT_bake_rotation(Operator):
    """Bake random rotation keyframes at each hero transition"""
    bl_idname = "herotracker.bake_rotation"
    bl_label = "Bake Rotation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.hero_tracker

        # Find hero empties
        empties_to_process = []
        for suffix in ['_fw', '_bw']:
            hero_name = f"HeroEmpty{suffix}"
            if hero_name in bpy.data.objects:
                hero = bpy.data.objects[hero_name]
                if hero.animation_data and hero.animation_data.action:
                    empties_to_process.append((suffix, hero))

        if not empties_to_process:
            self.report({'ERROR'}, "No animated HeroEmpty found. Bake hero track first.")
            return {'CANCELLED'}

        # Set up random seed
        if props.rotation_seed != 0:
            random.seed(props.rotation_seed)
        else:
            random.seed()

        stddev_rad = math.radians(props.rotation_stddev)
        total_keyframes = 0

        for suffix, hero_empty in empties_to_process:
            action = hero_empty.animation_data.action

            # Find the particle_index F-curve
            particle_index_fcurve = None
            for fcurve in action.fcurves:
                if fcurve.data_path == '["particle_index"]':
                    particle_index_fcurve = fcurve
                    break

            if particle_index_fcurve is None:
                continue

            # Find transition frames
            keyframes = particle_index_fcurve.keyframe_points
            if len(keyframes) < 2:
                continue

            transition_frames = []
            prev_value = None
            first_frame = None

            for kf in keyframes:
                frame = int(kf.co[0])
                value = int(kf.co[1])

                if first_frame is None:
                    first_frame = frame

                if prev_value is not None and value != prev_value:
                    transition_frames.append(frame)
                prev_value = value

            # Clear existing rotation keyframes
            for fcurve in list(action.fcurves):
                if fcurve.data_path == 'rotation_euler':
                    action.fcurves.remove(fcurve)

            hero_empty.rotation_mode = 'XYZ'

            all_rotation_frames = [first_frame] + transition_frames

            for frame in all_rotation_frames:
                rot_x = random.gauss(0, stddev_rad)
                rot_y = random.gauss(0, stddev_rad)
                rot_z = random.gauss(0, stddev_rad)

                hero_empty.rotation_euler = (rot_x, rot_y, rot_z)
                hero_empty.keyframe_insert(data_path="rotation_euler", frame=frame)

            for fcurve in action.fcurves:
                if fcurve.data_path == 'rotation_euler':
                    for keyframe in fcurve.keyframe_points:
                        keyframe.interpolation = 'BEZIER'
                        keyframe.handle_left_type = 'AUTO_CLAMPED'
                        keyframe.handle_right_type = 'AUTO_CLAMPED'

            total_keyframes += len(all_rotation_frames)

        self.report(
            {'INFO'},
            f"Baked rotation: {total_keyframes} keyframes across {len(empties_to_process)} empty(s)"
        )

        return {'FINISHED'}


class HEROTRACKER_OT_export_titles(Operator):
    """Export hero titles to Blender text editor (reads baked keyframes + CSV)"""
    bl_idname = "herotracker.export_titles"
    bl_label = "Export Hero Titles"
    bl_options = {'REGISTER'}

    def execute(self, context):
        global _paper_data
        props = context.scene.hero_tracker

        # Find hero empties with animation
        empties_to_export = []
        for suffix in ['_fw', '_bw']:
            hero_name = f"HeroEmpty{suffix}"
            hero = bpy.data.objects.get(hero_name)
            if hero and hero.animation_data and hero.animation_data.action:
                empties_to_export.append((suffix, hero))

        if not empties_to_export:
            self.report({'ERROR'}, "No animated HeroEmpty found. Bake first.")
            return {'CANCELLED'}

        # Ensure CSV data is loaded
        if not _paper_data:
            if not props.csv_file_path:
                self.report({'ERROR'}, "No CSV file set. Configure in Text Display section.")
                return {'CANCELLED'}
            if load_paper_csv(props.csv_file_path) == 0:
                self.report({'ERROR'}, f"Failed to load CSV: {props.csv_file_path}")
                return {'CANCELLED'}

        all_lines = ["HERO TRACKER - TITLE EXPORT", "=" * 50, ""]
        total_unique = 0

        for suffix, hero in empties_to_export:
            fcurve = None
            for fc in hero.animation_data.action.fcurves:
                if fc.data_path == '["particle_index"]':
                    fcurve = fc
                    break

            if not fcurve or len(fcurve.keyframe_points) == 0:
                continue

            all_lines.append(f"Track: HeroEmpty{suffix}")
            all_lines.append("-" * 30)

            segments = []
            prev_idx, start_frame = None, None

            for kf in fcurve.keyframe_points:
                frame, idx = int(kf.co[0]), int(kf.co[1])
                if idx != prev_idx:
                    if prev_idx is not None and prev_idx >= 0:
                        segments.append((start_frame, frame - 1, prev_idx))
                    prev_idx, start_frame = idx, frame

            if prev_idx is not None and prev_idx >= 0:
                segments.append((start_frame, int(fcurve.keyframe_points[-1].co[0]), prev_idx))

            seen, unique_titles = set(), []

            for start, end, idx in segments:
                paper = _paper_data.get(idx, {})
                title = paper.get('title', f'[No data for particle {idx}]')
                abstract = paper.get('abstract', '')
                all_lines.append(f"Frames {start}-{end} | Particle {idx}")
                all_lines.append(f"  Title: {title}")
                if abstract:
                    all_lines.append(f"  Abstract: {abstract}")
                all_lines.append("")
                if idx not in seen:
                    seen.add(idx)
                    unique_titles.append((idx, title))

            all_lines.append(f"Unique heroes: {len(unique_titles)}")
            all_lines.append("")
            total_unique += len(unique_titles)

        # Write to text block
        text_name = "HeroTitles"
        text = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
        text.clear()
        text.write("\n".join(all_lines))

        self.report({'INFO'}, f"Exported {total_unique} unique heroes to '{text_name}'")
        return {'FINISHED'}


# =============================================================================
# PROPERTIES
# =============================================================================

class HeroTrackerProperties(PropertyGroup):
    particle_system_name: StringProperty(
        name="Particle System",
        description="Name of the particle system to track",
        default="ParticleSystem"
    )

    camera_fw: PointerProperty(
        name="Camera (Forward)",
        description="Forward camera for hero tracking",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CAMERA'
    )

    camera_bw: PointerProperty(
        name="Camera (Backward)",
        description="Backward camera for hero tracking (optional - for seamless loops)",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'CAMERA'
    )

    selection_mode: EnumProperty(
        name="Selection Mode",
        description="How to select which particle to track",
        items=[
            ('CLOSEST', "Closest", "Track the particle closest to the camera"),
            ('LARGEST_ON_SCREEN', "Largest on Screen",
             "Track the particle with the largest apparent size (size/distance)"),
        ],
        default='CLOSEST'
    )

    view_margin: FloatProperty(
        name="View Margin",
        description=(
            "Margin for view frustum check (fraction of frame). "
            "Positive = include particles slightly outside frame. "
            "Negative = exclude particles near frame edges."
        ),
        default=0.0,
        min=-0.5,
        max=0.5,
        step=1,
        precision=2
    )

    switch_margin: FloatProperty(
        name="Switch Margin",
        description=(
            "Margin for hero switching (fraction of frame). "
            "Positive = keep tracking hero even when slightly outside frame. "
            "Negative = switch sooner, even when hero is still slightly inside frame."
        ),
        default=0.0,
        min=-0.5,
        max=0.5,
        step=1,
        precision=2
    )

    lookahead_frames: IntProperty(
        name="Lookahead Frames",
        description=(
            "When switching heroes, look this many frames into the future to pick "
            "the best particle. Creates natural entry animations as particles "
            "enter the frame. Set to 0 to disable lookahead."
        ),
        default=20,
        min=0,
        max=120
    )

    fade_frames: IntProperty(
        name="Fade Frames",
        description=(
            "Number of frames for opacity fade in/out around transitions. "
            "At the transition frame, opacity=0. N frames before/after, opacity=1. "
            "Blender interpolates between these keyframes."
        ),
        default=30,
        min=1
    )

    frame_step: IntProperty(
        name="Frame Step",
        description=(
            "Evaluate every N frames for faster baking. "
            "1 = every frame (most accurate), 2 = every other frame (~2x faster), "
            "Higher values give faster bakes. Blender interpolates between keyframes."
        ),
        default=1,
        min=1,
        soft_max=100
    )

    # Text display properties
    enable_text_display: BoolProperty(
        name="Enable Text Display",
        description=(
            "Create text objects that display the title and abstract "
            "of the currently tracked particle from a CSV file"
        ),
        default=False
    )

    csv_file_path: StringProperty(
        name="CSV File",
        description=(
            "Path to CSV file with paper data. "
            "Expected columns: cleaned_title, decoded_abstract"
        ),
        default="",
        subtype='FILE_PATH'
    )

    # Rotation randomization properties
    rotation_stddev: FloatProperty(
        name="Rotation Std Dev",
        description=(
            "Standard deviation for random rotation in degrees. "
            "Each axis gets an independent random offset from a Gaussian distribution."
        ),
        default=5.0,
        min=0.0,
        soft_max=45.0
    )

    rotation_seed: IntProperty(
        name="Rotation Seed",
        description=(
            "Random seed for reproducible rotations. "
            "Set to 0 for a different result each time."
        ),
        default=0,
        min=0
    )


# =============================================================================
# UI PANEL
# =============================================================================

class HEROTRACKER_PT_main(Panel):
    """Hero Tracker main panel"""
    bl_label = "Hero Tracker"
    bl_idname = "HEROTRACKER_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hero Tracker"

    def draw(self, context):
        layout = self.layout
        props = context.scene.hero_tracker

        # Settings
        box = layout.box()
        box.label(text="Settings", icon='SETTINGS')
        box.prop(props, "particle_system_name", icon='PARTICLES')
        box.prop(props, "camera_fw", icon='CAMERA_DATA')
        box.prop(props, "camera_bw", icon='CAMERA_DATA')

        # Show camera status
        if props.camera_fw and props.camera_bw:
            box.label(text="Dual camera mode (fw + bw)", icon='CHECKMARK')
        elif props.camera_fw:
            box.label(text="Forward camera only", icon='INFO')
        elif props.camera_bw:
            box.label(text="Backward camera only", icon='INFO')
        else:
            box.label(text="No camera selected", icon='ERROR')

        box.prop(props, "selection_mode")

        # Lookahead & Transitions
        box.separator()
        box.label(text="Lookahead & Transitions:", icon='TIME')
        box.prop(props, "lookahead_frames")
        if props.lookahead_frames > 0:
            box.label(text=f"Pick hero prominent in {props.lookahead_frames}f", icon='INFO')
        box.prop(props, "fade_frames")

        # Performance
        box.separator()
        box.label(text="Performance:", icon='SORTTIME')
        box.prop(props, "frame_step")
        if props.frame_step > 1:
            box.label(text=f"~{props.frame_step}x faster (positions interpolated)", icon='INFO')

        # Margins
        box.separator()
        box.label(text="Margins:", icon='FULLSCREEN_ENTER')
        box.prop(props, "view_margin")
        box.prop(props, "switch_margin")

        # Text Display (optional)
        layout.separator()
        box = layout.box()
        box.label(text="Text Display", icon='FONT_DATA')
        box.prop(props, "enable_text_display")

        if props.enable_text_display:
            box.prop(props, "csv_file_path")
            if _paper_data:
                box.label(text=f"Loaded: {len(_paper_data)} papers", icon='CHECKMARK')
            elif props.csv_file_path:
                box.label(text="CSV not loaded (bake to load)", icon='INFO')

            # Show text object status
            for suffix in ['_fw', '_bw']:
                text_name = f"HeroText{suffix}"
                if text_name in bpy.data.objects:
                    box.label(text=f"{text_name}: Created", icon='CHECKMARK')

            if update_hero_text in bpy.app.handlers.frame_change_post:
                box.label(text="Handler: Active", icon='CHECKMARK')

            box.separator()
            box.operator("herotracker.export_titles", icon='TEXT')

        # Rotation Randomization
        layout.separator()
        box = layout.box()
        box.label(text="Rotation Randomization", icon='ORIENTATION_GIMBAL')
        box.prop(props, "rotation_stddev")
        box.prop(props, "rotation_seed")
        box.operator("herotracker.bake_rotation", icon='FILE_REFRESH')

        layout.separator()

        # Actions
        box = layout.box()
        box.label(text="Actions", icon='ACTION')

        row = box.row(align=True)
        row.scale_y = 1.5
        row.operator("herotracker.bake", icon='RENDER_ANIMATION')

        box.operator("herotracker.clear", icon='X')

        # Status
        layout.separator()
        box = layout.box()
        box.label(text="Status", icon='INFO')

        # Check if particle system exists
        obj, psys_idx = find_particle_system_by_name(context, props.particle_system_name)
        if obj:
            box.label(text=f"Found: {obj.name}", icon='CHECKMARK')
            depsgraph = context.evaluated_depsgraph_get()
            obj_eval = obj.evaluated_get(depsgraph)
            if psys_idx < len(obj_eval.particle_systems):
                psys_eval = obj_eval.particle_systems[psys_idx]
                box.label(text=f"Particles: {len(psys_eval.particles)}")
        else:
            box.label(text="Particle system not found", icon='ERROR')

        # Check hero empties
        for suffix in ['_fw', '_bw']:
            hero_name = f"HeroEmpty{suffix}"
            if hero_name in bpy.data.objects:
                hero = bpy.data.objects[hero_name]
                has_anim = hero.animation_data is not None and hero.animation_data.action is not None
                if has_anim:
                    box.label(text=f"{hero_name}: Animated", icon='CHECKMARK')
                    if "particle_index" in hero:
                        box.label(text=f"  Index: {hero['particle_index']}")
                else:
                    box.label(text=f"{hero_name}: No animation", icon='DOT')


# =============================================================================
# REGISTRATION
# =============================================================================

classes = (
    HeroTrackerProperties,
    HEROTRACKER_OT_bake,
    HEROTRACKER_OT_clear,
    HEROTRACKER_OT_bake_rotation,
    HEROTRACKER_OT_export_titles,
    HEROTRACKER_PT_main,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.hero_tracker = PointerProperty(type=HeroTrackerProperties)
    print("Hero Tracker v3.1.0 registered")


def unregister():
    # Clean up text handler if registered
    global _paper_data
    if update_hero_text in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(update_hero_text)
    _paper_data = {}

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.hero_tracker
    print("Hero Tracker addon unregistered")


if __name__ == "__main__":
    register()
