# Seamless Loop Stitching: Technical Notes

## The Problem

Creating seamlessly looping videos of particle simulations where the particles don't naturally return to their starting positions.

## The Solution: Forward/Backward Camera Technique

We render two camera passes on the same circular orbit path:
- **Forward camera**: `100 * (frame / orbit_period)` - orbits clockwise
- **Backward camera**: `100 * (-frame / orbit_period)` - orbits counter-clockwise

The cameras meet at exactly two points:
- **0% position** (frame 0, 60000, etc.) - the starting point
- **50% position** (frame 30000) - the opposite side of the orbit

By stitching forward footage with backward footage (played in reverse), we create a video where:
1. The camera appears to orbit continuously
2. The simulation plays forward, then backward, returning to its starting state
3. The video loops seamlessly

## Frame Sequence Structure

For a **0% crossover** (crossover at orbit position 0%):

```
Output Video:
[Forward: frame 4 → frame 60004] [Backward REVERSED: frame 59979 → frame 4]
         ^                                ^                              ^
         |                                |                              |
     Video start                    Crossover splice                 Video end (loops to start)
```

For a **50% crossover** (crossover at orbit position 50%):

```
Output Video:
[Forward: frame 4 → frame 30004] [Backward REVERSED: frame 29979 → frame 4]
```

## Key Parameters

- **orbit_period**: 60000 frames for one complete orbit
- **step**: Frame interval (25 for smooth, 500 for quick tests)
- **crossover_frame**: Where forward switches to backward (target: 30000 or 60000)
- **skip_crossover**: Whether to skip the crossover frame in backward sequence (avoids duplicate)

## Issues Encountered and Solutions

### Issue 1: Harsh Crossover Transitions

**Symptom**: Visible "jump" at the crossover point where forward switches to backward.

**Cause**: The rendered frames don't include the exact meeting points (frame 0, 30000, 60000). At non-meeting frames, the two cameras are on opposite sides of the meeting point, creating a visual gap.

**Example with step 500**:
- Nearest frame to 60000 was 59504 (496 frames away)
- Forward camera at 59504: 99.17% position
- Backward camera at 59504: 0.83% position
- Visual gap: ~1.66% of orbit

**Solution**: Render frames as close as possible to the meeting points.
- Added frames 60004 and 60029 to the renders
- Frame 60004 is only 4 frames from meeting point (60000)
- Reduced visual gap from ~1.66% to ~0.013% for the crossover frame

### Issue 2: Step Size Still Matters at Splice

**Important realization**: Even with frame 60004 rendered, the splice gap is still limited by step size:

| Step Size | Splice Gap |
|-----------|------------|
| 500 | ~0.82% (forward 60004 → backward 59504) |
| 25 | ~0.03% (forward 60004 → backward 59979) |

The crossover FRAME being close to the meeting point helps one side of the splice, but the backward sequence still starts one step away.

### Issue 3: Camera Tracking Point Drift

**Symptom**: Subtle artefacts even when camera positions match.

**Cause**: The camera's "track to" target was subtly changing during the animation, causing slight framing differences between forward and backward passes.

**Solution**: Lock the camera tracking to a static point. This dramatically improved the crossover smoothness ("1000 times better").

### Issue 4: Stale Output Files

**Symptom**: Output frame count didn't match expected count.

**Cause**: The script doesn't clear the output directory before copying new frames, leaving stale files from previous runs.

**Solution**: Manually verify frame counts or clear output directories before re-running.

## Best Practices for Smooth Loops

1. **Render meeting point frames**: Include frames at or very near 0, 30000, and 60000
2. **Use smaller step sizes**: Step 25 gives ~27x smoother crossovers than step 500
3. **Lock camera tracking**: Use a static tracking point, not one that drifts
4. **Verify frame ranges**: Check that output matches expected forward→backward sequence

## Script Usage

```bash
# Single crossover
python3 stitch_loop.py fw_dir bw_dir output_dir --crossover 30000

# Both crossovers (50% and 0%)
python3 stitch_loop.py fw_dir bw_dir output_base --both-crossovers

# Dry run to see what would happen
python3 stitch_loop.py fw_dir bw_dir output_dir --dry-run

# Include crossover frame in both sequences (creates 1-frame pause)
python3 stitch_loop.py fw_dir bw_dir output_dir --no-skip-crossover
```

## Output Videos in This Folder

| Video | Step | Physics | Tracking | Notes |
|-------|------|---------|----------|-------|
| `*_25step_reference_v2_*` | 25 | Evolved | Dynamic | Smoothest step size |
| `*_500step_reference_only_v2_*` | 500 | Static | Dynamic | Reference particles only |
| `*_500step_static_track_*` | 500 | Static | Static | Best crossover quality |
| `*_500step_evolved_static_track_*` | 500 | Evolved | Static | Full simulation, static tracking |

## Future Improvements

1. **Render exact meeting frames**: Frame 0, 30000, 60000 would eliminate crossover gap entirely
2. **Motion blur consideration**: Disabled motion blur may help reduce artefacts
3. **Blend at crossover**: Could implement frame blending at splice point for smoother transition
4. **Clear output directory**: Script should optionally clear output before copying

---

*Generated during debugging session, January 2026*
