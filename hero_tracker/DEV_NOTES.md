# Hero Tracker Development Notes

## Planned Feature: Minimum Screen Radius Exit Criteria

### The Problem

Current exit criteria only triggers hero switch when the particle moves **out of frame**.

With a circular camera path (camera moves into galaxy then back out), when the camera pulls away:
- The hero particle **shrinks but stays on screen**
- Text becomes tiny and ugly
- Hero never switches because particle is technically still "in frame"

### Proposed Solution: `min_screen_radius` Property

Add a minimum screen radius threshold. When the particle's effective screen radius drops below this, trigger a hero switch (same as if it went out of frame).

### Implementation Plan

1. **Add new property** in `HeroTrackerProperties`:
   ```python
   min_screen_radius: FloatProperty(
       name="Min Screen Radius",
       description=(
           "Minimum screen radius (as fraction of frame) before triggering hero switch. "
           "Prevents text from shrinking too small when camera pulls away. "
           "0 = disabled, 0.02 = switch when particle is 2% of frame height."
       ),
       default=0.02,
       min=0.0,
       max=0.2,
       step=1,
       precision=3
   )
   ```

2. **Add new check function** inside `execute()`:
   ```python
   def is_hero_too_small(particle_data, camera):
       """Check if hero particle has shrunk below minimum visible size."""
       if particle_data is None:
           return True
       if min_screen_radius <= 0:
           return False  # Feature disabled

       screen_radius, _ = get_screen_radius(
           scene, camera, particle_data['location'], particle_data['size']
       )
       # Use effective radius (accounts for text spiral size)
       effective_radius = screen_radius * text_scale_factor
       return effective_radius < min_screen_radius
   ```

3. **Modify switch logic** to check BOTH conditions:
   ```python
   # Current:
   if is_hero_out_of_frame(current_hero_data, camera, switch_margin):
       # switch hero...

   # New:
   if is_hero_out_of_frame(current_hero_data, camera, switch_margin) or \
      is_hero_too_small(current_hero_data, camera):
       # switch hero...
   ```

4. **Add UI element** in Margins section:
   ```python
   box.prop(props, "min_screen_radius")
   ```

### How It Works With Existing Features

- **text_scale_factor**: The "too small" check uses `effective_radius = screen_radius * text_scale_factor`, so it accounts for text spiral size
- **Fade behavior**: Uses the same fade mechanism as out-of-frame switches (opacity keyframes)
- **switch_margin**: Independent - margin is for position, min_screen_radius is for size

### Default Value Rationale

`0.02` (2% of frame) chosen because:
- At 4K (3840px height), 2% = 77 pixels - still readable but getting small
- At 8K (4320px height), 2% = 86 pixels
- User can adjust based on their text size and render resolution

### Testing Notes

To test this feature:
1. Create a camera path that moves INTO the galaxy then BACK OUT
2. Set `min_screen_radius = 0.02`
3. Bake hero track
4. Verify that heroes switch when particles shrink below threshold (even if still on screen)
5. Verify fade works correctly at the switch point

---

## Current Version: 3.2.0

### Recent Changes (v3.2.0)
- Added `text_scale_factor` property to account for text spirals being larger than particles
- Modified `is_hero_out_of_frame()` to use `effective_radius = screen_radius * text_scale_factor`

### File Location
Main addon file: `hero_tracker/src/__init__.py`
Blender install: `~/Library/Application Support/Blender/4.5/scripts/addons/hero_tracker/__init__.py`

### Copy to Blender
```bash
cp /Users/mo/github/ucl_eye/hero_tracker/src/__init__.py \
   "/Users/mo/Library/Application Support/Blender/4.5/scripts/addons/hero_tracker/__init__.py"
```
