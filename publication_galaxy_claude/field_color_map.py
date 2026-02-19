#!/usr/bin/env python3
"""
Generate the UCL Eye Academic Field → Black Body Color Mapping figure.

Maps 284 field_level_1 categories (IDs 0-283) to blackbody temperatures
using MIRED (reciprocal temperature) scaling for better perceptual distribution.

MIRED mapping:
    frac = field_id / 283
    mired = 1/T_max + frac * (1/T_min - 1/T_max)
    T = 1 / mired

This spreads categories more evenly across the visible blackbody spectrum
instead of cramming everything into the blue end. Side effect: the mapping
is flipped — low field IDs (Medicine) map to blue, high IDs (Philosophy) to red.

T_min = 800K (avoids near-zero division), T_max = 35000K.

Output: field_color_map_labeled.png

Originally created in session c240463d (Feb 11, 2026).
MIRED scaling added Feb 17, 2026.
"""

import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


def blackbody_to_rgb(temp_k):
    """Convert blackbody temperature (Kelvin) to RGB (0-1 range).

    Uses Tanner Helland's approximation of the CIE 1931 chromaticity + Planckian locus.
    Note: Blender's internal blackbody may differ slightly.
    """
    if temp_k < 100:
        return (0, 0, 0)
    temp = temp_k / 100.0
    if temp <= 66:
        r = 255
    else:
        r = min(255, max(0, 329.698727446 * ((temp - 60) ** -0.1332047592)))
    if temp <= 66:
        g = min(255, max(0, 99.4708025861 * math.log(temp) - 161.1195681661))
    else:
        g = min(255, max(0, 288.1221695283 * ((temp - 60) ** -0.0755148492)))
    if temp >= 66:
        b = 255
    elif temp <= 19:
        b = 0
    else:
        b = min(255, max(0, 138.5177312231 * math.log(temp - 10) - 305.0447927307))
    return (r / 255, g / 255, b / 255)


# MIRED scaling parameters
T_MIN = 800      # Minimum temperature (K) — avoids division-by-zero, tuned for look
T_MAX = 60000    # Maximum temperature (K)
MAX_FIELD = 283  # Highest field ID


def field_id_to_temp(field_id):
    """Convert field ID (0-283) to blackbody temperature using MIRED scaling.

    Linear interpolation in reciprocal-temperature (MIRED) space:
        mired = 1/T_max + (field_id/283) * (1/T_min - 1/T_max)
        T = 1/mired

    This flips the mapping: field 0 → T_max (blue), field 283 → T_min (red).
    """
    frac = field_id / MAX_FIELD
    mired = 1.0 / T_MAX + frac * (1.0 / T_MIN - 1.0 / T_MAX)
    return 1.0 / mired


def temp_to_x(temp):
    """Convert temperature to x-axis position (MIRED-linear space).

    x-axis is linear in field_id (= linear in MIRED), flipped so red is left.
    x = MAX_FIELD - field_id, so x=0 → field 283 (800K, red), x=283 → field 0 (35000K, blue).
    """
    mired = 1.0 / temp
    mired_min = 1.0 / T_MAX  # blue end
    mired_max = 1.0 / T_MIN  # red end
    frac = (mired - mired_min) / (mired_max - mired_min)  # 0 at blue, 1 at red
    field_id = frac * MAX_FIELD
    return MAX_FIELD - field_id  # flip: red=left (x=0), blue=right (x=283)


# 19 parent categories sorted by frequency in dataset.
# IDs match GROUPED_FIELD_L1_IDS in molecular-plus/simulate.py
CATEGORIES = [
    (0, 40, "Medicine", "36%"),
    (41, 58, "Biology", "13%"),
    (59, 72, "Psychology", "11%"),
    (73, 126, "Computer Science", "9%"),
    (127, 146, "Chemistry", "6%"),
    (147, 162, "Physics", "7%"),
    (163, 175, "Materials Science", "7%"),
    (176, 187, "Sociology", "2%"),
    (188, 199, "Geology", "1%"),
    (200, 206, "Mathematics", "1.5%"),
    (207, 215, "Political Science", "2%"),
    (216, 231, "Business", "1%"),
    (232, 240, "Geography", "1%"),
    (241, 251, "Environmental Sci", "0.7%"),
    (252, 268, "Economics", "1%"),
    (269, 272, "History", "0.2%"),
    (273, 278, "Engineering", "0.3%"),
    (279, 282, "Art", "0.6%"),
    (283, 283, "Philosophy", "~0%"),
]


def generate_figure(output_path="field_color_map_labeled.png", dpi=150):
    import numpy as np

    fig, (ax_spec, ax_cats) = plt.subplots(
        2, 1, figsize=(16, 10),
        gridspec_kw={'height_ratios': [1, 3]},
        facecolor='#1a1a1a'
    )

    # X-axis is linear in MIRED space (field_id), range [0, MAX_FIELD].
    # x=0 → field 283 (T=800K, red, left), x=283 → field 0 (T=35000K, blue, right).

    # Top: continuous spectrum bar sampled in MIRED space
    gradient = np.zeros((50, 1000, 3))
    for px in range(1000):
        x = (px / 999) * MAX_FIELD
        field_id = MAX_FIELD - x  # x=0 → field 283 (red), x=283 → field 0 (blue)
        temp = field_id_to_temp(field_id)
        gradient[:, px] = blackbody_to_rgb(temp)
    ax_spec.imshow(gradient, aspect='auto', extent=[0, MAX_FIELD, 0, 1])
    ax_spec.set_xlim(0, MAX_FIELD)
    ax_spec.set_xlabel('Black Body Temperature (K)', color='white', fontsize=12)
    ax_spec.set_yticks([])
    ax_spec.tick_params(colors='white')
    ax_spec.set_facecolor('#1a1a1a')
    ax_spec.set_title(
        'UCL Eye: Academic Field \u2192 Black Body Color Mapping (MIRED Scale)',
        color='white', fontsize=16, fontweight='bold', pad=15
    )

    # Temperature tick labels at MIRED-spaced positions
    tick_temps = [800, 1000, 1500, 2000, 3000, 5000, 10000, 20000, 60000]
    tick_positions = [temp_to_x(t) for t in tick_temps]
    tick_labels = [f'{t // 1000}K' if t >= 1000 else f'{t}' for t in tick_temps]
    ax_spec.set_xticks(tick_positions)
    ax_spec.set_xticklabels(tick_labels, fontsize=10)

    # Bottom: category bars in MIRED-linear space
    ax_cats.set_facecolor('#1a1a1a')
    ax_cats.set_xlim(0, MAX_FIELD)
    ax_cats.set_ylim(-0.5, len(CATEGORIES) - 0.5)
    ax_cats.invert_yaxis()

    for i, (fid_start, fid_end, name, pct) in enumerate(CATEGORIES):
        # Position in MIRED-linear x space (red=left, blue=right)
        x_left = MAX_FIELD - fid_end     # red side of this category
        x_right = MAX_FIELD - fid_start  # blue side of this category
        bar_width = x_right - x_left
        x_mid = (x_left + x_right) / 2

        # Color from midpoint temperature
        mid_field_id = (fid_start + fid_end) / 2
        temp_mid = field_id_to_temp(mid_field_id)
        color = blackbody_to_rgb(temp_mid)

        rect = mpatches.FancyBboxPatch(
            (x_left, i - 0.35), bar_width, 0.7,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor='white', linewidth=0.5
        )
        ax_cats.add_patch(rect)

        # Label to the right of the bar
        label_x = x_right + 3
        if label_x + 40 > MAX_FIELD:
            label_x = x_left - 3
            ha = 'right'
        else:
            ha = 'left'

        ax_cats.text(
            label_x, i, f'{name}  (IDs {fid_start}-{fid_end}, {pct})',
            va='center', ha=ha, fontsize=9, color='white', fontweight='medium'
        )

        # Temperature label inside bar if wide enough
        brightness = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        if bar_width > 15:
            t_lo = int(min(field_id_to_temp(fid_start), field_id_to_temp(fid_end)))
            t_hi = int(max(field_id_to_temp(fid_start), field_id_to_temp(fid_end)))
            text_color = 'black' if brightness > 0.5 else 'white'
            ax_cats.text(
                x_mid, i, f'{t_lo}-{t_hi}K',
                va='center', ha='center', fontsize=7, color=text_color
            )

    ax_cats.set_yticks([])
    ax_cats.set_xticks(tick_positions)
    ax_cats.set_xticklabels(tick_labels, fontsize=10, color='white')
    ax_cats.tick_params(colors='white')
    ax_cats.set_xlabel('Black Body Temperature (K)', color='white', fontsize=12)

    for spine in ax_spec.spines.values():
        spine.set_color('#444')
    for spine in ax_cats.spines.values():
        spine.set_color('#444')

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, facecolor='#1a1a1a',
                bbox_inches='tight', pad_inches=0.3)
    print(f"Saved {output_path}")


def generate_figure_linear(output_path="field_color_map_linear.png", dpi=150):
    """Generate the legacy figure with linear temperature x-axis (pre-MIRED)."""
    import numpy as np

    linear_max = 35000

    fig, (ax_spec, ax_cats) = plt.subplots(
        2, 1, figsize=(16, 10),
        gridspec_kw={'height_ratios': [1, 3]},
        facecolor='#1a1a1a'
    )

    gradient = np.zeros((50, 1000, 3))
    for x in range(1000):
        temp = (x / 999) * linear_max
        gradient[:, x] = blackbody_to_rgb(temp)
    ax_spec.imshow(gradient, aspect='auto', extent=[0, linear_max, 0, 1])
    ax_spec.set_xlim(0, linear_max)
    ax_spec.set_xlabel('Black Body Temperature (K)', color='white', fontsize=12)
    ax_spec.set_yticks([])
    ax_spec.tick_params(colors='white')
    ax_spec.set_facecolor('#1a1a1a')
    ax_spec.set_title(
        'UCL Eye: Academic Field \u2192 Black Body Color Mapping (Linear Scale)',
        color='white', fontsize=16, fontweight='bold', pad=15
    )

    temps = [0, 5000, 10000, 15000, 20000, 25000, 30000, 35000]
    ax_spec.set_xticks(temps)
    ax_spec.set_xticklabels([f'{t // 1000}K' for t in temps], fontsize=10)

    ax_cats.set_facecolor('#1a1a1a')
    ax_cats.set_xlim(0, linear_max)
    ax_cats.set_ylim(-0.5, len(CATEGORIES) - 0.5)
    ax_cats.invert_yaxis()

    for i, (fid_start, fid_end, name, pct) in enumerate(CATEGORIES):
        t_start = field_id_to_temp(fid_start)
        t_end = field_id_to_temp(fid_end)
        t_lo, t_hi = min(t_start, t_end), max(t_start, t_end)
        t_mid = (t_lo + t_hi) / 2
        color = blackbody_to_rgb(t_mid)
        bar_width = t_hi - t_lo

        rect = mpatches.FancyBboxPatch(
            (t_lo, i - 0.35), bar_width, 0.7,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor='white', linewidth=0.5
        )
        ax_cats.add_patch(rect)

        label_x = t_hi + 300
        if label_x + 5000 > linear_max:
            label_x = t_lo - 300
            ha = 'right'
        else:
            ha = 'left'
        ax_cats.text(
            label_x, i, f'{name}  (IDs {fid_start}-{fid_end}, {pct})',
            va='center', ha=ha, fontsize=9, color='white', fontweight='medium'
        )

        brightness = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
        if bar_width > 2000:
            text_color = 'black' if brightness > 0.5 else 'white'
            ax_cats.text(
                t_mid, i, f'{int(t_lo)}-{int(t_hi)}K',
                va='center', ha='center', fontsize=7, color=text_color
            )

    ax_cats.set_yticks([])
    ax_cats.set_xticks(temps)
    ax_cats.set_xticklabels([f'{t // 1000}K' for t in temps], fontsize=10, color='white')
    ax_cats.tick_params(colors='white')
    ax_cats.set_xlabel('Black Body Temperature (K)', color='white', fontsize=12)

    for spine in ax_spec.spines.values():
        spine.set_color('#444')
    for spine in ax_cats.spines.values():
        spine.set_color('#444')

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, facecolor='#1a1a1a',
                bbox_inches='tight', pad_inches=0.3)
    print(f"Saved {output_path}")


def print_table():
    """Print a text table of the MIRED mapping."""
    print(f"\n{'Field IDs':<12} {'Temp Range (K)':<20} {'Category':<18} {'RGB (mid)'}")
    print("-" * 75)
    for fid_start, fid_end, name, pct in CATEGORIES:
        t_start = field_id_to_temp(fid_start)
        t_end = field_id_to_temp(fid_end)
        t_lo, t_hi = min(t_start, t_end), max(t_start, t_end)
        t_mid = (t_lo + t_hi) / 2
        r, g, b = blackbody_to_rgb(t_mid)
        print(f"{fid_start:>3}-{fid_end:<8} {int(t_lo):>5} - {int(t_hi):<13} {name:<18} "
              f"({int(r * 255):>3}, {int(g * 255):>3}, {int(b * 255):>3})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate field → blackbody color map figure")
    parser.add_argument("-o", "--output", default="field_color_map_labeled.png",
                        help="Output PNG path (default: field_color_map_labeled.png)")
    parser.add_argument("--dpi", type=int, default=150, help="Figure DPI (default: 150)")
    parser.add_argument("--table", action="store_true", help="Also print text table")
    parser.add_argument("--linear", action="store_true",
                        help="Also generate legacy linear-scale figure for comparison")
    args = parser.parse_args()

    generate_figure(args.output, args.dpi)
    if args.linear:
        linear_path = args.output.replace('.png', '_linear.png')
        generate_figure_linear(linear_path, args.dpi)
    if args.table:
        print_table()
