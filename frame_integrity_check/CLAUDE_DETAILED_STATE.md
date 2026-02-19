# Frame Integrity Check — Consolidated State

Central documentation for all corruption detection, verification, and remediation across the 130K-frame 8K seamless loop render (render 16, 32-sample). Superseded by render 17 (256-sample).

## Corruption Taxonomy

Five distinct corruption types were discovered across the 130K-frame render:

| # | Type | Severity | Detection Method | Cause | Count |
|---|------|----------|-----------------|-------|-------|
| 1 | **Scanline corruption** | High — visible glitches, broken pixels | `oiiotool --printstats` reports "unable to compute" or "corrupt"; DaVinci shows "media offline" | Blender crash/GPU fault mid-write. EXR partially written. | ~80+ frames |
| 2 | **Camera flip** | Critical — wrong viewpoint | `oiiotool --diff bw.exr fw.exr` → RMS < 0.01 means BW frame matches FW camera | Blender bug: BW renders used FW camera for frames 31026-65998 | ~17,500 frames |
| 3 | **Subtle data corruption** | Low-Medium — invisible to eye, detectable by pixel diff | Re-render + `oiiotool --diff old.exr new.exr` → mean_err >> 1.0 | Unknown GPU/memory fault. Frame looks fine but pixel values wrong. | 5 confirmed |
| 4 | **Zero-size placeholders** | High — black frame | `os.path.getsize() == 0` | Blender crash leaves 0-byte file; Blender then skips it on restart (thinks it's rendered) | 4+ frames |
| 5 | **JPG-only (missing EXR)** | Medium — JPG exists, EXR missing | Check for `.exr` alongside `.jpg` | Blender writes JPG first, EXR second. Crash between writes loses EXR. Also: corrected step-1 renders not writing EXR for step-2 fill frames. | 1,719+ frames |

## Detection Methods

### Definitive: Re-render Comparison (Type 3 gold standard)
```bash
oiiotool old.exr new.exr --diff
```
- **Clean frame**: mean_err ~1e-05 (GPU floating-point noise between renders)
- **Corrupt frame**: mean_err >> 1.0 (e.g., frame 45: 2.999e+07, frame 8936: 2.319e+01)
- This is the ONLY reliable method for subtle corruption (Type 3)

### Fast: oiiotool printstats (Type 1)
```bash
oiiotool frame.exr --printstats
```
- Look for "unable to compute", "corrupt", or error in stderr
- Catches scanline corruption only, not subtle data issues

### Fast: Camera Flip Detection (Type 2)
```bash
oiiotool bw_frame.exr fw_frame.exr --diff
```
- RMS < 0.01 = same image = wrong camera was used
- Only applies to BW frames that should differ from FW

### Fast: File-based checks (Types 4 & 5)
- Zero-size: `os.path.getsize(path) == 0`
- Missing EXR: check for `.exr` file alongside each `.jpg`

### Unreliable: Neighbor Ratio Method (DO NOT rely on)
Compares frame vs neighbor brightness/StdDev, then baseline neighbor-vs-neighbor. Ratios of 2-4x overlap between genuinely corrupt and clean frames. **Cannot distinguish corruption from natural scene variation.** Only useful as a first-pass filter to narrow candidates for re-render comparison.

## All Confirmed Corrupt Frames

### Type 1: Scanline Corruption

#### D1 FW (Mo 4TB) — 4 frames
| Frame | Status |
|-------|--------|
| 51076 | Re-rendered, verified clean |
| 51077 | Re-rendered, verified clean |
| 53764 | Re-rendered, verified clean |
| 59012 | Re-rendered, verified clean |
| 59652 | Re-rendered, verified clean |

#### D2 FW (Mo 4TB 2) — 5 frames
| Frame | Status |
|-------|--------|
| 23430 | Re-rendered, verified clean |
| 23687 | Re-rendered, verified clean |
| 24964 | Re-rendered |
| 24970 | Re-rendered, verified clean |
| 32772 | Re-rendered, verified clean (meeting frame) |
| 43908 | Re-rendered |
| 48132 | Re-rendered, verified clean |

#### D3 BW (Mo 4TB 3) — 34+ frames
| Frame | Status |
|-------|--------|
| 35676 | Re-rendered, verified clean |
| 36245, 36246, 36269 | Re-rendered, verified clean |
| 37765, 37766, 37767, 37794, 37801, 37802 | Re-rendered, verified clean |
| 47327, 47407, 47540, 47637, 47639 | Re-rendered, verified clean |
| 48553, 48555, 48602, 48605, 48615, 48618, 48943 | Re-rendered, verified clean |
| 49719, 49730, 49777 | Re-rendered, verified clean |
| 56660, 59183, 59187, 59191, 59668, 59934, 59938 | Re-rendered, verified clean |
| 60379, 60383, 60387, 60391, 60742, 60944 | Re-rendered, verified clean |
| 61478, 61482, 61486, 61490, 61861, 61865 | Re-rendered, verified clean |
| 62031, 62035, 62245, 62375, 62379 | Re-rendered, verified clean |
| 63382, 63386, 64024 | Re-rendered, verified clean |

#### D4 BW (Mo 4TB 4) — 30+ frames
| Frame | Status |
|-------|--------|
| 7689, 9482, 9742, 9754, 9998 | Re-rendered, verified clean |
| 11271, 11277, 11283, 11285, 11291, 11369, 11381 | Re-rendered, verified clean |
| 11397-11405 (5 odd frames) | Re-rendered, verified clean |
| 11407-11417 (6 odd frames) | **Deleted, needs 2nd render pass** |
| 20826, 20833, 21083 | **Deleted, needs 2nd render pass** |
| 21457, 21461, 21483, 21727 | **Deleted, needs 2nd render pass** |
| 22246, 22250 | **Deleted, needs 2nd render pass** |
| 1032, 1927, 2823 | **Deleted, needs 2nd render pass** |
| 4105, 4231, 4612, 4617 | **Deleted, needs 2nd render pass** |
| 5382, 5386, 6662, 6926 | **Deleted, needs 2nd render pass** |

### Type 2: Camera Flip
- **Range**: BW frames 31026-65998 (step-2 and step-1 fills)
- **Resolution**: JPGs deleted to force re-render with correct BW camera
- **Status**: Corrected. ~17,500 wrong-camera frames replaced.
- Full frame list in `wrong_camera_frames.json`

### Type 3: Subtle Data Corruption (confirmed by re-render comparison)

| Frame | Drive | mean_err (old vs new) | Description |
|-------|-------|----------------------|-------------|
| 45 | D4 BW | 2.999e+07 | Zeros in Depth channel |
| 8936 | D4 BW | 2.319e+01 | Subtle pixel corruption |
| 40683 | D3 BW | 3200 | Subtle pixel corruption |
| 44325 | D3 BW | 2411 | Subtle pixel corruption |
| 62178 | D3 BW | 15232 | Subtle pixel corruption |

All 5 were re-rendered and verified clean. Originals archived to NAS.

**Note**: 97 other flagged anomaly frames tested clean (mean_err ~1e-05) — they were natural scene variation, not corruption.

### Type 4: Zero-Size Placeholders
From `rerender_manifest.json`:
- Frames 30217, 30233, 40217, 40233

### Type 5: JPG-Only Missing EXR
- 1,719 step-2 fill frames (31026-52998, every 4th) on D3 — see `rerender_manifest.json`
- 91 step-1 fill frames (32557-32737, odd) on D3 — see `rerender_manifest.json`

## Anomaly Scan Summary (151 flagged, 5 confirmed corrupt)

Two-phase statistical scan across all 4 drives flagged 151 frames with unusual brightness/StdDev:
- **D1 FW**: 4 flagged, 0 confirmed corrupt (all natural variation)
- **D2 FW**: 46 flagged, 0 confirmed corrupt (all natural variation)
- **D3 BW**: 72 flagged, 3 confirmed corrupt (frames 40683, 44325, 62178)
- **D4 BW**: 30 flagged, 2 confirmed corrupt (frames 45, 8936)

Staging and verification completed for D3 and D4. D2 staged but superseded by render 17. D1 not staged (superseded).

Original anomaly frames archived to NAS at:
`/Volumes/Datasets Toshibas/ucl_eye/render_soft_launch/staging_anomaly_d3/` and `d4/`

## Scripts Inventory

All scripts are in this folder (`frame_integrity_check/`).

| Script | Purpose | Usage |
|--------|---------|-------|
| `check_frames.py` | JPG-based statistical outlier detection using numpy/PIL. MAD-based z-scores for brightness, contrast, file size. Original integrity checker. | `python3 check_frames.py <jpg_dir>` |
| `anomaly_scan.py` | Two-phase EXR anomaly detection. Phase 1: file size indexing (fast). Phase 2: `oiiotool --printstats` brightness/StdDev comparison for flagged frames. | `python3 anomaly_scan.py` (edit DRIVES list at top) |
| `corruption_test.py` | Neighbor-ratio corruption test. Compares frame-vs-neighbor error vs baseline. **Proven unreliable** for subtle corruption — ratios overlap. Only useful as rough filter. | `python3 corruption_test.py` (reads `/tmp/anomaly_scan_results.json`) |
| `full_exr_scan.py` | Sequential `oiiotool --printstats` scan of every EXR on a drive. Catches Type 1 (scanline) corruption. | `python3 full_exr_scan.py` (edit `exr_dir` at top) |

## Data Files

| File | Contents |
|------|----------|
| `rerender_manifest.json` | Machine-readable lists: `missing_exr` (1,719), `corrupt_bw_d3` (4), `corrupt_bw_d4` (1), `corrupt_fw_d2` (2), `missing_exr_step1` (91), `zero_byte_placeholders` (4) |
| `wrong_camera_frames.json` | Full list of BW frames rendered with wrong (FW) camera |
| `RERENDER_NOTES.md` | Detailed per-frame log of all scanline corruption found during DaVinci grading, with status |
| `results/anomaly_scan_results.json` | 151 anomaly entries from two-phase scan |
| `results/corruption_test_results.json` | Neighbor-ratio test results (unreliable — see above) |
| `results/results_16_final_path_bw_no_hero.json` | Full JPG-based scan results for BW pass |
| `results/results_16_final_path_fw_no_hero.json` | Full JPG-based scan results for FW pass |

## Drive Layout (render 16, as of Feb 10 2026)

| Drive | Label | Contents | EXR Dir |
|-------|-------|----------|---------|
| Mo 4TB | D1 FW | Forward pass (partial) + symlinks + DaVinci | `16_final_path_fw_no_hero_EXR` |
| Mo 4TB 2 | D2 FW | Forward pass complete (50,059 frames) | `16_final_path_fw_no_hero_EXR` |
| Mo 4TB 3 | D3 BW | Backward 22,666-66,000 | `16_final_path_bw_no_hero_EXR` |
| Mo 4TB 4 | D4 BW | Backward 4-22,664 (step-1 complete) | `16_final_path_bw_no_hero_EXR` |

## Key Lessons Learned

1. **Re-render comparison is the only definitive corruption test.** Statistical methods (brightness/StdDev deviation, neighbor ratios) can flag candidates but cannot confirm — natural scene variation overlaps with subtle corruption.

2. **Corruption is rare but real.** Out of ~130K frames, ~80+ had scanline corruption (visible), 5 had subtle data corruption (invisible to eye), ~17,500 had wrong camera (systematic bug), and a handful had zero-size or missing EXR files.

3. **Blender's skip-if-JPG-exists logic is a double-edged sword.** It prevents re-rendering completed frames, but also means a corrupt JPG (or zero-size placeholder) will never be fixed automatically — you must delete the JPG to force re-render.

4. **Cluster patterns exist.** Scanline corruption tends to occur in clusters of adjacent frames (e.g., 11397-11417, 60379-60391) — likely caused by a single GPU fault affecting a batch boundary.

5. **Concurrent rendering at 4 processes is optimal.** 5+ causes GPU contention on Mac Studio M3 Ultra, dropping throughput by ~30%.
