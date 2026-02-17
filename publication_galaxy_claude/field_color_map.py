#!/usr/bin/env python3
"""
Generate the UCL Eye Academic Field → Black Body Color Mapping figure.

Maps 284 field_level_1 categories (IDs 0-283) to blackbody temperatures (0-30,000K)
and produces a labeled visualization showing the spectrum and category bands.

Output: field_color_map_labeled.png

Originally created in session c240463d (Feb 11, 2026).
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

MAX_FIELD = 283
MAX_TEMP = 30000


def generate_figure(output_path="field_color_map_labeled.png", dpi=150):
    import numpy as np

    fig, (ax_spec, ax_cats) = plt.subplots(
        2, 1, figsize=(16, 10),
        gridspec_kw={'height_ratios': [1, 3]},
        facecolor='#1a1a1a'
    )

    # Top: continuous spectrum bar
    gradient = np.zeros((50, 1000, 3))
    for x in range(1000):
        temp = (x / 999) * MAX_TEMP
        gradient[:, x] = blackbody_to_rgb(temp)
    ax_spec.imshow(gradient, aspect='auto', extent=[0, MAX_TEMP, 0, 1])
    ax_spec.set_xlim(0, MAX_TEMP)
    ax_spec.set_xlabel('Black Body Temperature (K)', color='white', fontsize=12)
    ax_spec.set_yticks([])
    ax_spec.tick_params(colors='white')
    ax_spec.set_facecolor('#1a1a1a')
    ax_spec.set_title(
        'UCL Eye: Academic Field \u2192 Black Body Color Mapping',
        color='white', fontsize=16, fontweight='bold', pad=15
    )

    temps = [0, 5000, 10000, 15000, 20000, 25000, 30000]
    ax_spec.set_xticks(temps)
    ax_spec.set_xticklabels([f'{t // 1000}K' for t in temps], fontsize=10)

    # Bottom: category bars
    ax_cats.set_facecolor('#1a1a1a')
    ax_cats.set_xlim(0, MAX_TEMP)
    ax_cats.set_ylim(-0.5, len(CATEGORIES) - 0.5)
    ax_cats.invert_yaxis()

    for i, (fid_start, fid_end, name, pct) in enumerate(CATEGORIES):
        t_start = (fid_start / MAX_FIELD) * MAX_TEMP
        t_end = (fid_end / MAX_FIELD) * MAX_TEMP
        t_mid = (t_start + t_end) / 2
        color = blackbody_to_rgb(t_mid)

        bar_width = t_end - t_start
        rect = mpatches.FancyBboxPatch(
            (t_start, i - 0.35), bar_width, 0.7,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor='white', linewidth=0.5
        )
        ax_cats.add_patch(rect)

        # Label to the right of the bar
        label_x = t_end + 200
        brightness = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]

        ax_cats.text(
            label_x, i, f'{name}  (IDs {fid_start}-{fid_end}, {pct})',
            va='center', ha='left', fontsize=9, color='white', fontweight='medium'
        )

        # Temperature label inside bar if wide enough
        if bar_width > 2000:
            text_color = 'black' if brightness > 0.5 else 'white'
            ax_cats.text(
                t_mid, i, f'{int(t_start)}-{int(t_end)}K',
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
    """Print a text table of the mapping."""
    print(f"\n{'Field IDs':<12} {'Temp Range (K)':<20} {'Category':<18} {'RGB (mid)'}")
    print("-" * 75)
    for fid_start, fid_end, name, pct in CATEGORIES:
        t_start = int((fid_start / MAX_FIELD) * MAX_TEMP)
        t_end = int((fid_end / MAX_FIELD) * MAX_TEMP)
        t_mid = (t_start + t_end) // 2
        r, g, b = blackbody_to_rgb(t_mid)
        print(f"{fid_start:>3}-{fid_end:<8} {t_start:>5} - {t_end:<13} {name:<18} "
              f"({int(r * 255):>3}, {int(g * 255):>3}, {int(b * 255):>3})")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate field → blackbody color map figure")
    parser.add_argument("-o", "--output", default="field_color_map_labeled.png",
                        help="Output PNG path (default: field_color_map_labeled.png)")
    parser.add_argument("--dpi", type=int, default=150, help="Figure DPI (default: 150)")
    parser.add_argument("--table", action="store_true", help="Also print text table")
    args = parser.parse_args()

    generate_figure(args.output, args.dpi)
    if args.table:
        print_table()
