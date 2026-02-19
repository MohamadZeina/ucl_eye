# Frames Moved for Re-Render (Feb 8 2026)

JPGs moved to `_rerender_staging/` on each drive so Blender will re-render them with both JPG + EXR.

## 1. Step-2 frames missing EXR (1,719 frames)

**Drive**: Mo 4TB 3
**Moved from**: `16_final_path_bw_no_hero/`
**Moved to**: `_rerender_staging/`
**Range**: 31026 to 52998 (every 4th frame, step-2 only)
**Why**: These were originally wrong-camera frames. JPGs were deleted, corrected renders on Feb 7 re-created JPGs, but then a bulk EXR deletion (clearing wrong-camera EXRs) accidentally deleted the freshly rendered correct EXRs too. The Feb 8 renders fixed this, but the Feb 7 batch needs re-doing.
**After re-render**: Should have both JPG + EXR. No further verification needed — these are straightforward re-renders with the correct camera (already verified).

## 2. Corrupted frames — NEED RE-CHECK AFTER RE-RENDER (7 frames)

These had the correct camera but bad render output (batch boundary glitches, brightness anomalies). After re-rendering, run the integrity checker on these specific frames to confirm the corruption doesn't recur.

### BW on Mo 4TB 3 (4 frames)
**Moved from**: `16_final_path_bw_no_hero/`
**Moved to**: `_rerender_staging/`

| Frame | Issue |
|-------|-------|
| 23270 | Too dim (brightness ~18 vs expected ~30) |
| 25005 | Statistical anomaly (corrupted output) |
| 25707 | Too dim (brightness 24.6 vs expected 32.0) |
| 55680 | Too bright (brightness 20.7 vs neighbors at 8.5, step-4 batch boundary) |

### BW on Mo 4TB 4 (1 frame)
**Moved from**: `16_final_path_bw_no_hero/`
**Moved to**: `_rerender_staging/`

| Frame | Issue |
|-------|-------|
| 2697 | Too bright (brightness 65 vs expected ~40) |

### FW on Mo 4TB 2 (2 frames)
**Moved from**: `16_final_path_fw_no_hero/`
**Moved to**: `_rerender_staging/`

| Frame | Issue |
|-------|-------|
| 23430 | Too bright, missing shadows/AO |
| 24970 | Too bright, missing shadows/AO |

## 3. Frames with no JPG (already missing — no action taken)

These frames have no JPG on disk, so Blender will render them automatically. Listed here for completeness.

| Frames | Count | Drive | Why missing |
|--------|-------|-------|-------------|
| 22667, 22669, 22670 | 3 | Mo 4TB 3 | Wrong-camera deletion, behind all frontiers |
| 25711-25861 (odd only) | 76 | Mo 4TB 3 | Wrong-camera deletion, behind all frontiers |

## Summary

| Category | Count | Drive | Action after re-render |
|----------|-------|-------|----------------------|
| Missing EXR (step-2) | 1,719 | Mo 4TB 3 BW | None — straightforward |
| Corrupt BW | 4 | Mo 4TB 3 BW | Re-check with integrity scanner |
| Corrupt BW | 1 | Mo 4TB 4 BW | Re-check with integrity scanner |
| Corrupt FW | 2 | Mo 4TB 2 FW | Re-check with integrity scanner |
| Already missing | 79 | Mo 4TB 3 BW | Re-check not needed |
| **Total** | **1,805** | | |

## Manifest

Machine-readable frame list: `rerender_manifest.json`

## Staging folder locations

- `/Volumes/Mo 4TB 2/render/_rerender_staging/` (2 FW JPGs)
- `/Volumes/Mo 4TB 3/render/_rerender_staging/` (1,723 BW JPGs)
- `/Volumes/Mo 4TB 4/render/_rerender_staging/` (1 BW JPG)

Once re-renders are verified, these staging folders can be deleted.

## After the D3 BW render (started from 22665)

That render covers ALL D3 gaps (7,410 frames) including the 4 corrupt D3 frames.

**Still need separate renders:**

| Frame | Direction | Drive | Render dir |
|-------|-----------|-------|------------|
| 2697 | BW | Mo 4TB 4 | `16_final_path_bw_no_hero` |
| 23430 | FW | Mo 4TB 2 | `16_final_path_fw_no_hero` |
| 24970 | FW | Mo 4TB 2 | `16_final_path_fw_no_hero` |

All 3 are corrupt frames (correct camera, bad render output). Re-check after rendering.

## Corrupted EXRs found during DaVinci grading (Feb 9)

These were discovered via DaVinci "media offline" errors and the fine-tooth-comb scan. JPG + EXR deleted directly (not staged) to allow immediate re-render.

| Frame | Direction | Drive | Issue | Status |
|-------|-----------|-------|-------|--------|
| 32772 | FW | Mo 4TB 2 | Corrupted scanline chunks, brightness 6.44 vs 40.17 (meeting frame) | Re-rendered, verified clean |
| 35676 | BW | Mo 4TB 3 | Corrupted scanline chunks | Re-rendered, verified clean |
| 23687 | FW | Mo 4TB 2 | Corrupted scanline chunks, brightness half of neighbors | Re-rendered, verified clean |
| 2697 | BW | Mo 4TB 4 | Missing EXR (never re-created after staging) | Re-rendered, verified clean |
| 24964 | FW | Mo 4TB 2 | Corrupted scanline chunks, all-zero pixels | Re-rendered (Feb 10 10:30) |
| 43908 | FW | Mo 4TB 2 | Corrupted scanline chunks (TC 12:11:44) | Re-rendered by active Blender |
| 48132 | FW | Mo 4TB 2 | Corrupted scanline chunks (TC 13:22:08) | Re-rendered, verified clean |
| 51076 | FW | Mo 4TB | Corrupted scanline chunks (TC 14:11:12) | Re-rendered, verified clean |
| 51077 | FW | Mo 4TB | Corrupted scanline chunks (adjacent to 51076) | Re-rendered, verified clean |
| 53764 | FW | Mo 4TB | Corrupted scanline chunks (TC 14:56:00) | Re-rendered, verified clean |
| 59012 | FW | Mo 4TB | Corrupted scanline chunks (TC 16:23:28) | Re-rendered, verified clean |
| 59652 | FW | Mo 4TB | Corrupted scanline chunks (TC 16:34:08) | Re-rendered, verified clean |
| 64024 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 18:37:32) | Re-rendered, verified clean |
| 9998 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 33:37:58) | Re-rendered, verified clean (correct BW camera) |
| 11271 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent cluster) | Re-rendered, verified clean |
| 11277 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent cluster) | Re-rendered, verified clean |
| 11283 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent to 11285) | Re-rendered, verified clean |
| 11285 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 33:16:31) | Re-rendered, verified clean |
| 11291 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent cluster) | Re-rendered, verified clean |
| 11369 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent cluster) | Re-rendered, verified clean |
| 11381 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent cluster) | Re-rendered, verified clean |
| 11397-11405 (odd) | BW | Mo 4TB 4 | 5 of 11 corrupt, every-other-frame cluster (TC 33:14:19) | Re-rendered, verified clean |
| 11407-11417 (odd) | BW | Mo 4TB 4 | 6 of 11 corrupt, cluster continues | **Deleted, needs 2nd render pass** |
| 20826 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 30:37:30, adjacent to 20833) | **Deleted, needs 2nd render pass** |
| 20833 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 30:37:23) | **Deleted, needs 2nd render pass** |
| 21083 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 30:33:13) | **Deleted, needs 2nd render pass** |
| 21457 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 30:26:59) | **Deleted, needs 2nd render pass** |
| 21461 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent to 21457) | **Deleted, needs 2nd render pass** |
| 21483 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 30:26:33) | **Deleted, needs 2nd render pass** |
| 21727 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 30:22:29) | **Deleted, needs 2nd render pass** |
| 22246 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 30:13:50) | **Deleted, needs 2nd render pass** |
| 22250 | BW | Mo 4TB 4 | Corrupted scanline chunks (adjacent to 22246) | **Deleted, needs 2nd render pass** |
| 1032 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 36:07:24) | **Deleted, needs 2nd render pass** |
| 1927 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 35:52:29) | **Deleted, needs 2nd render pass** |
| 2823 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 35:37:33) | **Deleted, needs 2nd render pass** |
| 4105 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 35:14:05) | **Deleted, needs 2nd render pass** |
| 4231 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 35:14:05 area) | **Deleted, needs 2nd render pass** |
| 4612 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 35:07:44) | **Deleted, needs 2nd render pass** |
| 4617 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 35:07:39) | **Deleted, needs 2nd render pass** |
| 5382 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 34:54:54) | **Deleted, needs 2nd render pass** |
| 5386 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 34:54:50) | **Deleted, needs 2nd render pass** |
| 6662 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 34:33:34) | **Deleted, needs 2nd render pass** |
| 6926 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 34:29:10) | **Deleted, needs 2nd render pass** |
| 7689 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 34:16:27) | Re-rendered, verified clean |
| 9482 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 33:46:34) | Re-rendered, verified clean |
| 9742 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 33:42:14) | Re-rendered, verified clean |
| 9754 | BW | Mo 4TB 4 | Corrupted scanline chunks (TC 33:42:02) | Re-rendered, verified clean |
| 36245 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 26:20:31) | Re-rendered, verified clean |
| 36246 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 26:20:30) | Re-rendered, verified clean |
| 36269 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 26:20:07) | Re-rendered, verified clean |
| 37765 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 37767) | Re-rendered, verified clean |
| 37766 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 37767) | Re-rendered, verified clean |
| 37767 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 25:55:09) | Re-rendered, verified clean |
| 37794 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 25:54:42, adjacent to 37802) | Re-rendered, verified clean |
| 37801 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 37802) | Re-rendered, verified clean |
| 37802 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 25:54:34) | Re-rendered, verified clean |
| 47327 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 23:15:49) | Re-rendered, verified clean |
| 47407 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 23:14:29) | Re-rendered, verified clean |
| 47540 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 23:12:16) | Re-rendered, verified clean |
| 47637 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 23:10:39) | Re-rendered, verified clean |
| 47639 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 23:10:37) | Re-rendered, verified clean |
| 48553 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:55:23, adjacent to 48555) | Re-rendered, verified clean |
| 48555 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:55:21) | Re-rendered, verified clean |
| 48602 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 48615) | Re-rendered, verified clean |
| 48605 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 48615) | Re-rendered, verified clean |
| 48615 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:54:21) | Re-rendered, verified clean |
| 48618 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:54:18) | Re-rendered, verified clean |
| 48943 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:48:53) | Re-rendered, verified clean |
| 49719 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:35:57, adjacent to 49730) | Re-rendered, verified clean |
| 49730 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:35:46) | Re-rendered, verified clean |
| 49777 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 22:34:59) | Re-rendered, verified clean |
| 56660 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 20:40:16) | Re-rendered, verified clean |
| 59183 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 59191, step-4) | Re-rendered, verified clean |
| 59187 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 59191, step-4) | Re-rendered, verified clean |
| 59191 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:58:05) | Re-rendered, verified clean |
| 59668 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:50:08) | Re-rendered, verified clean |
| 59934 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:45:42) | Re-rendered, verified clean |
| 59938 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 59934) | Re-rendered, verified clean |
| 60379 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:38:17, step-4 cluster) | Re-rendered, verified clean |
| 60383 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:38:13, step-4 cluster) | Re-rendered, verified clean |
| 60387 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:38:09, step-4 cluster) | Re-rendered, verified clean |
| 60391 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:38:05, step-4 cluster) | Re-rendered, verified clean |
| 60742 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:32:14) | Re-rendered, verified clean |
| 60944 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:28:52) | Re-rendered, verified clean |
| 61478 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent, step-4 pattern) | Re-rendered, verified clean |
| 61482 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent, step-4 pattern) | Re-rendered, verified clean |
| 61486 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent, step-4 pattern) | Re-rendered, verified clean |
| 61490 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:19:46) | Re-rendered, verified clean |
| 61861 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:13:35, adjacent to 61865) | Re-rendered, verified clean |
| 61865 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:13:31) | Re-rendered, verified clean |
| 62031 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:10:45, adjacent to 62035) | Re-rendered, verified clean |
| 62035 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:10:41) | Re-rendered, verified clean |
| 62245 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:07:11) | Re-rendered, verified clean |
| 62375 | BW | Mo 4TB 3 | Corrupted scanline chunks (adjacent to 62379) | Re-rendered, verified clean |
| 62379 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 19:04:57) | Re-rendered, verified clean |
| 63382 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 18:48:14, adjacent to 63386) | Re-rendered, verified clean |
| 63386 | BW | Mo 4TB 3 | Corrupted scanline chunks (TC 18:48:10) | Re-rendered, verified clean |
