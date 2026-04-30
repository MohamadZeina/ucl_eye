#!/usr/bin/env python3
"""
Star Dropout Corruption Scanner

Detects frames where bright pixels (stars) temporarily go black then recover.
This is a render artifact where a few samples produce incorrect near-black
pixels for exactly one frame.

Detection pattern (for frame N):
  Frame N-1: pixel is bright (value > BRIGHT_THRESH)
  Frame N:   pixel is dark   (value < DARK_THRESH)
  Frame N+1: pixel recovers  (value > RECOVER_THRESH)

Also detects the inverse: pixels that flash bright for one frame.

Saves comprehensive per-frame metrics so the scan never needs repeating.
Flagged frames include pixel-level detail for manual review.

Usage:
    python3 star_dropout_scanner.py --jpg-dir /path/to/jpgs --output results.json
    python3 star_dropout_scanner.py --jpg-dir /path --output results.json --workers 2
"""

import os
import sys
import json
import time
import argparse
import numpy as np
from pathlib import Path
from PIL import Image
from concurrent.futures import ProcessPoolExecutor

# ─── Configuration ─────────────────────────────────────────────────────────

# Downscale factor for initial scan (8K / DOWNSCALE)
# At /4: 1760x810 — fast but still resolves individual stars
DOWNSCALE = 4

# Thresholds (on 0-255 uint8 scale, applied to max RGB channel)
BRIGHT_THRESH = 40    # pixel considered "bright" if any channel > this
DARK_THRESH = 12      # pixel considered "dark" if all channels < this
RECOVER_THRESH = 30   # pixel considered "recovered" if any channel > this

# Flagging
FLAG_DROPOUT_MIN = 3         # flag if >= this many dropout pixels
FLAG_FLASHBRIGHT_MIN = 3     # flag if >= this many flash-bright pixels
DETAIL_TOP_N = 50            # save pixel-level detail for top N worst pixels per frame

# Full-res analysis for flagged frames
FULLRES_THRESH = 20          # do full-res check if downscaled count >= this


# ─── Core detection ────────────────────────────────────────────────────────

def load_frame(path, downscale=DOWNSCALE):
    """Load and downscale a JPG frame."""
    img = Image.open(path)
    if downscale > 1:
        w, h = img.size
        img = img.resize((w // downscale, h // downscale), Image.BILINEAR)
    return np.array(img, dtype=np.uint8)


def detect_dropouts(prev, curr, nxt):
    """
    Detect star dropout and flash-bright pixels.

    Returns dict with counts and pixel details.
    """
    prev_f = prev.astype(np.float32)
    curr_f = curr.astype(np.float32)
    nxt_f = nxt.astype(np.float32)

    # Max channel per pixel (for brightness check)
    prev_max = np.max(prev, axis=2)
    curr_max = np.max(curr, axis=2)
    nxt_max = np.max(nxt, axis=2)

    # Min channel per pixel (for darkness check — all channels must be dark)
    curr_min_ch = np.min(curr, axis=2)
    prev_min_ch = np.min(prev, axis=2)

    # --- Star dropout: bright → dark → bright ---
    was_bright = prev_max > BRIGHT_THRESH
    is_dark = curr_max < DARK_THRESH
    will_recover = nxt_max > RECOVER_THRESH

    dropout_mask = was_bright & is_dark & will_recover
    dropout_count = int(np.sum(dropout_mask))

    # --- Flash bright: dark → bright → dark ---
    was_dark = prev_max < DARK_THRESH
    is_bright = curr_max > BRIGHT_THRESH * 2  # higher threshold for flash
    will_darken = nxt_max < DARK_THRESH

    # More specifically: pixels that spike up then return
    prev_was_dim = prev_max < BRIGHT_THRESH
    nxt_is_dim = nxt_max < BRIGHT_THRESH
    curr_is_very_bright = curr_max > BRIGHT_THRESH * 3

    flash_mask = prev_was_dim & curr_is_very_bright & nxt_is_dim
    flash_count = int(np.sum(flash_mask))

    # --- Compute drop magnitudes for dropouts ---
    drop = prev_f - curr_f  # positive = got darker
    drop_at_dropouts = drop[dropout_mask] if dropout_count > 0 else np.array([])

    result = {
        'dropout_count': dropout_count,
        'flash_count': flash_count,
        'max_drop': float(np.max(drop_at_dropouts)) if dropout_count > 0 else 0.0,
        'mean_drop': float(np.mean(drop_at_dropouts)) if dropout_count > 0 else 0.0,
    }

    # Save pixel details for flagged frames
    if dropout_count >= FLAG_DROPOUT_MIN:
        coords = np.where(dropout_mask)
        # Sort by drop magnitude (worst first)
        drops = [float(np.max(drop[coords[0][i], coords[1][i]])) for i in range(len(coords[0]))]
        order = np.argsort(drops)[::-1]

        details = []
        for idx in order[:DETAIL_TOP_N]:
            y, x = int(coords[0][idx]), int(coords[1][idx])
            details.append({
                'x': x * DOWNSCALE, 'y': y * DOWNSCALE,  # map back to full res coords
                'prev': prev[y, x].tolist(),
                'curr': curr[y, x].tolist(),
                'next': nxt[y, x].tolist(),
                'drop': drops[idx],
            })
        result['dropout_details'] = details

    if flash_count >= FLAG_FLASHBRIGHT_MIN:
        coords = np.where(flash_mask)
        details = []
        for i in range(min(DETAIL_TOP_N, len(coords[0]))):
            y, x = int(coords[0][i]), int(coords[1][i])
            details.append({
                'x': x * DOWNSCALE, 'y': y * DOWNSCALE,
                'prev': prev[y, x].tolist(),
                'curr': curr[y, x].tolist(),
                'next': nxt[y, x].tolist(),
            })
        result['flash_details'] = details

    return result


def scan_frame_triplet(args):
    """Process a single frame triplet. Used by multiprocessing."""
    prev_path, curr_path, next_path, frame_num = args
    try:
        prev = load_frame(prev_path)
        curr = load_frame(curr_path)
        nxt = load_frame(next_path)
        result = detect_dropouts(prev, curr, nxt)
        result['frame'] = frame_num
        return result
    except Exception as e:
        return {'frame': frame_num, 'error': str(e), 'dropout_count': 0, 'flash_count': 0}


# ─── Main scanner ──────────────────────────────────────────────────────────

def scan_pass(jpg_dir, output_path, workers=1, pass_label=""):
    """Scan an entire render pass for star dropout corruption."""
    jpg_dir = Path(jpg_dir)

    # Collect all valid frames
    frames = []
    for f in os.listdir(jpg_dir):
        if f.endswith('.jpg') and not f.startswith('.'):
            try:
                num = int(f.replace('.jpg', ''))
                path = jpg_dir / f
                if os.path.getsize(path) > 0:
                    frames.append((num, str(path)))
            except:
                pass

    frames.sort()
    total = len(frames)
    print(f"\n{'='*60}", flush=True)
    print(f"  Star Dropout Scanner: {pass_label}", flush=True)
    print(f"  Directory: {jpg_dir}", flush=True)
    print(f"  Frames: {total} ({frames[0][0]}..{frames[-1][0]})", flush=True)
    print(f"  Downscale: {DOWNSCALE}x, Workers: {workers}", flush=True)
    print(f"  Output: {output_path}", flush=True)
    print(f"{'='*60}\n", flush=True)

    # Build triplets
    triplets = []
    for i in range(1, len(frames) - 1):
        prev_num, prev_path = frames[i - 1]
        curr_num, curr_path = frames[i]
        next_num, next_path = frames[i + 1]

        # Only compare within contiguous sequences (no big gaps)
        if curr_num - prev_num <= 2 and next_num - curr_num <= 2:
            triplets.append((prev_path, curr_path, next_path, curr_num))

    print(f"Triplets to scan: {len(triplets)}", flush=True)

    # Scan
    results = []
    flagged_dropouts = []
    flagged_flashes = []
    t0 = time.time()

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, result in enumerate(pool.map(scan_frame_triplet, triplets, chunksize=50)):
                results.append(result)
                if result.get('dropout_count', 0) >= FLAG_DROPOUT_MIN:
                    flagged_dropouts.append(result)
                if result.get('flash_count', 0) >= FLAG_FLASHBRIGHT_MIN:
                    flagged_flashes.append(result)

                if (i + 1) % 1000 == 0:
                    elapsed = time.time() - t0
                    rate = (i + 1) / elapsed
                    eta_min = (len(triplets) - i - 1) / rate / 60
                    print(f"  [{time.strftime('%H:%M:%S')}] {i+1}/{len(triplets)} "
                          f"({rate:.0f}/s, ETA {eta_min:.0f}min) | "
                          f"Flagged: {len(flagged_dropouts)} dropouts, {len(flagged_flashes)} flashes",
                          flush=True)
    else:
        for i, triplet in enumerate(triplets):
            result = scan_frame_triplet(triplet)
            results.append(result)
            if result.get('dropout_count', 0) >= FLAG_DROPOUT_MIN:
                flagged_dropouts.append(result)
            if result.get('flash_count', 0) >= FLAG_FLASHBRIGHT_MIN:
                flagged_flashes.append(result)

            if (i + 1) % 500 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta_min = (len(triplets) - i - 1) / rate / 60
                print(f"  [{time.strftime('%H:%M:%S')}] {i+1}/{len(triplets)} "
                      f"({rate:.0f}/s, ETA {eta_min:.0f}min) | "
                      f"Flagged: {len(flagged_dropouts)} dropouts, {len(flagged_flashes)} flashes",
                      flush=True)

    elapsed = time.time() - t0

    # Compute statistics
    dropout_counts = [r.get('dropout_count', 0) for r in results]
    flash_counts = [r.get('flash_count', 0) for r in results]

    summary = {
        'pass_label': pass_label,
        'jpg_dir': str(jpg_dir),
        'total_frames': total,
        'triplets_scanned': len(triplets),
        'scan_time_seconds': round(elapsed, 1),
        'scan_time_human': f"{elapsed/3600:.1f}h" if elapsed > 3600 else f"{elapsed/60:.1f}min",
        'downscale': DOWNSCALE,
        'thresholds': {
            'bright': BRIGHT_THRESH,
            'dark': DARK_THRESH,
            'recover': RECOVER_THRESH,
            'flag_dropout_min': FLAG_DROPOUT_MIN,
            'flag_flash_min': FLAG_FLASHBRIGHT_MIN,
        },
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'flagged_dropout_count': len(flagged_dropouts),
        'flagged_flash_count': len(flagged_flashes),
        'dropout_stats': {
            'max': int(max(dropout_counts)) if dropout_counts else 0,
            'mean': round(sum(dropout_counts) / len(dropout_counts), 2) if dropout_counts else 0,
            'p99': int(np.percentile(dropout_counts, 99)) if dropout_counts else 0,
            'p999': int(np.percentile(dropout_counts, 99.9)) if dropout_counts else 0,
            'nonzero_frames': sum(1 for c in dropout_counts if c > 0),
        },
    }

    # Sort flagged by severity
    flagged_dropouts.sort(key=lambda r: -r.get('dropout_count', 0))
    flagged_flashes.sort(key=lambda r: -r.get('flash_count', 0))

    # Save everything
    output = {
        'summary': summary,
        'flagged_dropouts': flagged_dropouts,
        'flagged_flashes': flagged_flashes,
        'per_frame_counts': {str(r['frame']): {
            'dropout': r.get('dropout_count', 0),
            'flash': r.get('flash_count', 0),
            'max_drop': r.get('max_drop', 0),
        } for r in results},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\n{'='*60}", flush=True)
    print(f"  SCAN COMPLETE: {pass_label}", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Scanned: {len(triplets)} triplets in {summary['scan_time_human']}", flush=True)
    print(f"  Flagged dropouts: {len(flagged_dropouts)}", flush=True)
    print(f"  Flagged flashes:  {len(flagged_flashes)}", flush=True)
    print(f"  Dropout stats: max={summary['dropout_stats']['max']}, "
          f"p99={summary['dropout_stats']['p99']}, "
          f"nonzero={summary['dropout_stats']['nonzero_frames']}", flush=True)

    if flagged_dropouts:
        print(f"\n  Top flagged dropout frames:", flush=True)
        for r in flagged_dropouts[:20]:
            print(f"    Frame {r['frame']}: {r['dropout_count']} dropouts, "
                  f"max_drop={r.get('max_drop', 0):.0f}", flush=True)

    print(f"\n  Results saved: {output_path}", flush=True)
    return output


# ─── Entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Star dropout corruption scanner')
    parser.add_argument('--jpg-dir', required=True, help='JPG directory to scan')
    parser.add_argument('--output', required=True, help='Output JSON path')
    parser.add_argument('--workers', type=int, default=1, help='Parallel workers (default: 1)')
    parser.add_argument('--label', default='', help='Pass label for reporting')
    args = parser.parse_args()

    scan_pass(args.jpg_dir, args.output, workers=args.workers, pass_label=args.label)


if __name__ == '__main__':
    main()
