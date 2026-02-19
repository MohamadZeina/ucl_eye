# Seamless Loop Stitching: Technical Notes

## The Problem

Creating seamlessly looping videos of particle simulations where the particles don't naturally return to their starting positions.

## The Solution: Forward/Backward Camera Technique

We render two camera passes on the same circular orbit path:
- **Forward camera**: `100 * ((frame - 4) / 65536) + 2.8037` - orbits clockwise
- **Backward camera**: `100 * (-(frame - 4) / 65536) + 2.8037` - orbits counter-clockwise

The `- 4` shifts meeting frames to {4, 32772, 65540} (avoiding frame 0/2 artefacts).
The `+ 2.8037` is a phase offset that rotates the visual crossover position on the orbit by ~2.8% (~10°) without changing which simulation frames the cameras meet at.

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

### Issue 3: Camera Tracking Point (Static vs Moving)

**Initial symptom**: Severe artefacts at crossover points even when camera positions should match.

**Original setup**:
- Forward camera tracks to a "forward empty" orbiting a small circle
- Backward camera tracks to a "backward empty" orbiting the same small circle in reverse
- Both empties should meet at the same points as the cameras (0%, 50%)

**Initial hypothesis**: Moving empties compound the visual discontinuity because at the splice point, not only are the cameras offset from the meeting point, but the look-targets are also offset in the same direction, roughly doubling the viewing angle difference.

**Testing revealed**: When switched to a static tracking point, crossovers became "1000 times better" - nearly flawless.

**However**: Further testing with corrected implementation showed moving focus points can also work flawlessly. The original issue may have been an implementation bug (e.g., cameras looking at wrong empties) rather than a fundamental problem with the technique.

**Current status**: Both static and moving focus points appear to work when implemented correctly. Static is simpler and guaranteed to work; moving focus requires careful setup but can provide subtle parallax effects.

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
| `*_500step_static_track_*` | 500 | Static | Static | Reference only, static focus |
| `*_500step_evolved_static_track_*` | 500 | Evolved | Static | Full simulation, static focus |
| `*_500step_static_track_large_ref_*` | 500 | Evolved | Static | Large reference particles, static focus |
| `*_500step_static_track_large_ref_only_*` | 500 | Static | Static | Large reference only, static focus |
| `*_500step_moving_focus_large_ref_only_*` | 500 | Static | Moving | Large reference only, moving focus |
| `*_500step_moving_focus_evolved_large_ref_*` | 500 | Evolved | Moving | Full simulation, moving focus |
| `*_500step_try_repro_*` | 500 | Evolved | Moving | Reproduction test for moving focus |

## Phase Offset for Crossover Position

To change where on the orbit the crossover happens (without changing which simulation frames are used), add a phase offset to the camera driver:

```
# Original (crossover at 0% and 50% of orbit visually)
100 * ((frame - 4) / 65536)

# With phase offset (rotates visual crossover position)
100 * ((frame - 4) / 65536) + phase_offset

# General formula
100 * ((frame - N) / period) + phase_offset
```

Apply the same offset to both cameras:
- Forward: `100 * ((frame - 4) / 65536) + 2.8037`
- Backward: `100 * (-(frame - 4) / 65536) + 2.8037`

The cameras still meet at the same simulation frames {4, 32772, 65540}, but the visual position on the orbit where they meet shifts by `phase_offset / 100 * 360°` (2.8037% ≈ 10°).

## Shifting Meeting Frames (Skip Artefacts)

If certain simulation frames have rendering artefacts (e.g., frame 0 or 2), you can shift which frames the cameras meet at using a **negative** offset:

```
# Original: cameras meet at frames 0, period/2, period
Forward:  100 * (frame / period)
Backward: 100 * (-frame / period)

# Shifted by N frames: cameras meet at frames N, period/2 + N, period + N
Forward:  100 * ((frame - N) / period)
Backward: 100 * (-(frame - N) / period)
```

**Example**: To skip frame 2 artefact with period 65536, plus visual phase offset:
- Forward: `100 * ((frame - 4) / 65536) + 2.8037`
- Backward: `100 * (-(frame - 4) / 65536) + 2.8037`

This shifts meeting frames from {0, 32768, 65536} to {4, 32772, 65540}.

**Key**: Both formulas use subtraction (minus N). This ensures:
- At frame 4: both cameras are at position 0% (meet)
- At frame 32772: both cameras are at position 50% (meet)
- At frame 65540: both cameras are at position 100%/0% (meet, loop point)

## Future Improvements

1. **Render exact meeting frames**: Frame 0, 30000, 60000 would eliminate crossover gap entirely
2. **Motion blur consideration**: Disabled motion blur may help reduce artefacts
3. **Blend at crossover**: Could implement frame blending at splice point for smoother transition
4. **Clear output directory**: Script should optionally clear output before copying

---

## Render Performance Benchmarks (January 2026)

### Hardware
- **Machine**: Mac Studio M3 Ultra (512GB RAM)
- **GPU**: M3 Ultra integrated GPU
- **Baseline single render**: ~11.0-11.5s/frame

### Concurrent Render Scaling

| Config | Interval | f/min | f/day | Parallel Eff | TB/day |
|--------|----------|-------|-------|--------------|--------|
| 1 (baseline) | 11.0s | 5.5 | 7,855 | 100% | 1.07 |
| 2 concurrent | 6.2s | 9.7 | 13,935 | 93% | 1.90 |
| 3 concurrent | 5.2s | 11.5 | 16,615 | 74% | 2.26 |
| 4 concurrent | 4.4s | 13.6 | 19,636 | 65% | 2.67 |
| 5 concurrent | 5.9s | 10.2 | 14,644 | 39% | 1.99 |

**Key finding**: 4 concurrent is optimal. 5 concurrent causes GPU contention and is slower than 4.

### Drive Performance Impact

The same drive in different enclosures showed dramatic performance differences:

| Enclosure | Rate | Effective Concurrent | TB/day |
|-----------|------|---------------------|--------|
| USB2 enclosure (~40 MB/s) | 10.5s/f | 1.9 of 3 | 1.12 |
| TerraMaster D4 DAS (40 Gbps) | 4.3s/f | 2.7 of 3 | 2.73 |
| **D4 DAS with 4 concurrent** | **3.8s/f** | **3.1 of 4** | **3.13** |
| D4 DAS with 5 concurrent | 4.3s/f | 2.7 of 5 | 2.74 |

**Key findings**:
- USB2 enclosure was severe bottleneck. Same drive in USB4/TB3 DAS achieved **2.4x faster** render throughput. The drive wasn't slow - the enclosure was.
- **4 concurrent on D4 DAS is optimal** (3.8s/f, 3.13 TB/day, 23K frames/day)
- 5 concurrent provides no benefit - GPU saturated at 4

### Storage Requirements

Per-frame sizes:
- JPG only: ~10 MB
- EXR (multi-layer): ~126 MB
- Combined: ~136 MB/frame

For 130K frames (full FW+BW passes):
- JPG only: 1.3 TB
- JPG + EXR: 17.7 TB

### Write Bandwidth Requirements

At 4 concurrent @ 4.4s/frame with JPG+EXR:
- Burst: ~544 MB every 4.4s = 124 MB/s peak
- USB2 capacity: ~40 MB/s (bottleneck!)
- USB 3.1: ~400 MB/s (3.2x headroom)
- USB 3.2/TB3: ~800+ MB/s (adequate)

---

*Generated during debugging session, January 2026*
