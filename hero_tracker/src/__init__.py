"""
Hero Tracker - Blender Addon

Finds the most prominent particle in camera view and tracks it with an empty.
For each frame, identifies which particle from a named particle system is
closest to the camera while being within the camera's view frustum.

Custom properties baked on HeroEmpty:
- particle_index: Which particle is currently tracked
- opacity: Fades out/in during transitions (for text display)
- particle_distance: Distance from camera to particle
- screen_x, screen_y: Normalized screen coordinates (0-1)
- is_transition: 1 if particle changed this frame, 0 otherwise

Usage:
1. Name your particle system (e.g., "GalaxyParticles")
2. Open the N-panel > Hero Tracker tab
3. Enter the particle system name
4. Select your camera
5. Click "Bake Hero Track"
6. An empty called "HeroEmpty" will be keyframed to follow the most prominent particle
"""

bl_info = {
    "name": "Hero Tracker",
    "author": "UCL Eye Project",
    "version": (1, 2, 0),
    "blender": (4, 0, 0),
    "location": "View3D > N-Panel > Hero Tracker",
    "description": "Track the most prominent particle in camera view with an empty",
    "category": "Animation",
}

import bpy
import array
import math
from mathutils import Vector
from bpy.props import StringProperty, FloatProperty, IntProperty, PointerProperty, EnumProperty
from bpy.types import Panel, Operator, PropertyGroup


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


def get_or_create_hero_empty(context):
    """
    Get or create the HeroEmpty object.
    Returns the empty object.
    """
    hero_name = "HeroEmpty"

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

        if not props.camera:
            self.report({'ERROR'}, "Please select a camera")
            return {'CANCELLED'}

        # Find particle system
        obj, psys_idx = find_particle_system_by_name(context, props.particle_system_name)
        if obj is None:
            self.report({'ERROR'}, f"Particle system '{props.particle_system_name}' not found")
            return {'CANCELLED'}

        camera = props.camera
        margin = props.view_margin
        fade_frames = props.fade_frames
        selection_mode = props.selection_mode

        # Get or create hero empty
        hero_empty = get_or_create_hero_empty(context)

        # Clear existing animation data
        if hero_empty.animation_data:
            hero_empty.animation_data_clear()

        # Initialize custom properties
        initialize_custom_properties(hero_empty)

        # Get frame range
        frame_start = scene.frame_start
        frame_end = scene.frame_end

        # Store current frame to restore later
        original_frame = scene.frame_current

        # First pass: collect all frame data
        frame_data = []
        for frame in range(frame_start, frame_end + 1):
            scene.frame_set(frame)
            particle = find_most_prominent_particle(context, obj, psys_idx, camera, margin, selection_mode)
            frame_data.append({
                'frame': frame,
                'particle': particle,
            })

        # Detect transitions
        prev_idx = None
        transition_frames = []
        for fd in frame_data:
            if fd['particle'] is not None:
                curr_idx = fd['particle']['index']
                if prev_idx is not None and curr_idx != prev_idx:
                    transition_frames.append(fd['frame'])
                prev_idx = curr_idx

        # Second pass: bake keyframes with fade logic
        frames_with_particle = 0
        frames_without_particle = 0

        for fd in frame_data:
            frame = fd['frame']
            particle = fd['particle']

            if particle is not None:
                # Set position
                hero_empty.location = particle['location']
                hero_empty.keyframe_insert(data_path="location", frame=frame)

                # Set scale based on particle size
                scale_val = max(particle['size'], 0.01)
                hero_empty.scale = (scale_val, scale_val, scale_val)
                hero_empty.keyframe_insert(data_path="scale", frame=frame)

                # Keyframe custom properties
                keyframe_custom_property(hero_empty, 'particle_index', particle['index'], frame)
                keyframe_custom_property(hero_empty, 'particle_distance', particle['distance'], frame)
                keyframe_custom_property(hero_empty, 'screen_x', particle['screen_x'], frame)
                keyframe_custom_property(hero_empty, 'screen_y', particle['screen_y'], frame)

                # is_transition
                is_trans = 1 if frame in transition_frames else 0
                keyframe_custom_property(hero_empty, 'is_transition', is_trans, frame)

                frames_with_particle += 1
            else:
                frames_without_particle += 1

        # Third pass: calculate opacity for each frame based on distance to transitions
        # This handles overlapping fades correctly

        def calculate_opacity(frame, transitions, fade_len):
            """Calculate opacity based on distance to nearest transition."""
            if not transitions:
                return 1.0

            min_dist = float('inf')
            for t in transitions:
                dist = abs(frame - t)
                if dist < min_dist:
                    min_dist = dist

            if min_dist >= fade_len:
                return 1.0  # Fully visible
            else:
                # Linear fade: 0 at transition, 1 at fade_len frames away
                return min_dist / fade_len

        # Calculate and keyframe opacity for each frame with a particle
        prev_opacity = None
        for fd in frame_data:
            if fd['particle'] is None:
                continue

            frame = fd['frame']
            opacity = calculate_opacity(frame, transition_frames, fade_frames)

            # Only keyframe if value changed (reduces keyframe count)
            if prev_opacity is None or abs(opacity - prev_opacity) > 0.001:
                keyframe_custom_property(hero_empty, 'opacity', opacity, frame)
                prev_opacity = opacity

        # Set interpolation to linear for opacity (smoother fades)
        if hero_empty.animation_data and hero_empty.animation_data.action:
            for fcurve in hero_empty.animation_data.action.fcurves:
                if 'opacity' in fcurve.data_path:
                    for keyframe in fcurve.keyframe_points:
                        keyframe.interpolation = 'LINEAR'
                # Use constant interpolation for particle_index (discrete values)
                elif 'particle_index' in fcurve.data_path or 'is_transition' in fcurve.data_path:
                    for keyframe in fcurve.keyframe_points:
                        keyframe.interpolation = 'CONSTANT'

        # Restore original frame
        scene.frame_set(original_frame)

        # Report results
        total_frames = frame_end - frame_start + 1
        mode_name = "closest" if selection_mode == 'CLOSEST' else "largest on screen"
        self.report(
            {'INFO'},
            f"Baked {frames_with_particle}/{total_frames} frames ({mode_name}). "
            f"{len(transition_frames)} transitions with {fade_frames}-frame fades."
        )

        return {'FINISHED'}


class HEROTRACKER_OT_clear(Operator):
    """Clear hero empty animation"""
    bl_idname = "herotracker.clear"
    bl_label = "Clear Animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        hero_name = "HeroEmpty"

        if hero_name in bpy.data.objects:
            hero = bpy.data.objects[hero_name]
            if hero.animation_data:
                hero.animation_data_clear()
                self.report({'INFO'}, "Animation cleared")
            else:
                self.report({'INFO'}, "No animation to clear")
        else:
            self.report({'WARNING'}, "HeroEmpty not found")

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

    camera: PointerProperty(
        name="Camera",
        description="Camera to use for view frustum calculations",
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

    fade_frames: IntProperty(
        name="Fade Frames",
        description="Number of frames to fade out/in during particle transitions",
        default=3,
        min=1,
        max=30
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
        box.prop(props, "camera", icon='CAMERA_DATA')
        box.prop(props, "selection_mode")
        box.prop(props, "view_margin")
        box.prop(props, "fade_frames")

        # Info about margin
        if props.view_margin != 0:
            if props.view_margin > 0:
                box.label(text=f"Including {props.view_margin*100:.0f}% outside frame", icon='INFO')
            else:
                box.label(text=f"Excluding {abs(props.view_margin)*100:.0f}% at edges", icon='INFO')

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

        # Check if HeroEmpty exists and show custom properties
        if "HeroEmpty" in bpy.data.objects:
            hero = bpy.data.objects["HeroEmpty"]
            has_anim = hero.animation_data is not None and hero.animation_data.action is not None
            if has_anim:
                box.label(text="HeroEmpty: Animated", icon='CHECKMARK')
                # Show current custom property values
                if "particle_index" in hero:
                    box.label(text=f"  Index: {hero['particle_index']}")
                if "opacity" in hero:
                    box.label(text=f"  Opacity: {hero['opacity']:.2f}")
            else:
                box.label(text="HeroEmpty: No animation", icon='DOT')
        else:
            box.label(text="HeroEmpty: Not created", icon='DOT')


# =============================================================================
# REGISTRATION
# =============================================================================

classes = (
    HeroTrackerProperties,
    HEROTRACKER_OT_bake,
    HEROTRACKER_OT_clear,
    HEROTRACKER_PT_main,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.hero_tracker = PointerProperty(type=HeroTrackerProperties)
    print("Hero Tracker v1.2.0 registered")


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.hero_tracker
    print("Hero Tracker addon unregistered")


if __name__ == "__main__":
    register()
