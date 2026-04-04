#!/usr/bin/env python3
"""
Merge FRONT/ADJ/BEHIND orientation variants in RSI directories into single states.

SS13 used separate FRONT/BEHIND sprites for z-ordering (behind vs in front of body).
In SS14, these are complementary - BEHIND has south/east/west frames, FRONT has north.
This script composites them into single combined sprites.

For each group of states sharing the same base name and color layer:
  - Composites all orientation PNGs (alpha-over blending)
  - Writes a single merged PNG without the position suffix
  - Updates meta.json with merged state entries
  - Removes old orientation-specific files and entries

Usage:
    python merge_rsi_orientations.py Resources/Textures/_Nova/Mobs/Customization/tails.rsi
    python merge_rsi_orientations.py Resources/Textures/_Nova/Mobs/Customization/ears.rsi
"""

import json
import os
import re
import sys
from collections import defaultdict
from PIL import Image


def merge_rsi(rsi_dir: str):
    meta_path = os.path.join(rsi_dir, 'meta.json')
    with open(meta_path) as f:
        meta = json.load(f)

    sprite_w = meta['size']['x']
    sprite_h = meta['size']['y']

    # Group states: (base, color) -> {pos: state_entry}
    # base includes any prefix like "waggingtail_"
    # Only group states with the same frame count (don't mix animated with static)
    groups = defaultdict(dict)
    state_map = {}  # state_name -> state_entry

    for s in meta['states']:
        name = s['name']
        state_map[name] = s

        # Parse color suffix
        color_match = re.match(r'^(.+)_(primary|secondary|tertiary)$', name)
        if color_match:
            rest, color = color_match.group(1), '_' + color_match.group(2)
        else:
            rest, color = name, ''

        # Parse position suffix
        pos_match = re.match(r'^(.+)_(FRONT|ADJ|BEHIND)$', rest)
        if pos_match:
            base, pos = pos_match.group(1), pos_match.group(2)
        else:
            base, pos = rest, 'NONE'

        # Include frame count in key so animated and static don't merge
        frame_count = len(s['delays'][0]) if 'delays' in s and s['delays'] else 1
        groups[(base, color, frame_count)][pos] = name

    # Find groups that need merging (have multiple positions)
    to_merge = {k: v for k, v in groups.items() if len(v) > 1}
    if not to_merge:
        print(f"  No orientations to merge in {rsi_dir}")
        return

    print(f"  Merging {len(to_merge)} state groups...")

    new_states = []
    states_to_remove = set()
    files_to_remove = set()

    # Process single-position states first (keep as-is)
    for (base, color, fc), positions in groups.items():
        if len(positions) == 1:
            pos = list(positions.keys())[0]
            state_name = positions[pos]
            new_states.append(state_map[state_name])

    # Process multi-position groups
    for (base, color, fc), positions in sorted(to_merge.items()):
        # Merged state name: base + color (no position suffix)
        merged_name = base + color

        # Composite PNGs: load all position variants and alpha-over blend
        merged_img = None
        merged_entry = None

        for pos in ['BEHIND', 'ADJ', 'NONE', 'FRONT']:
            if pos not in positions:
                continue
            state_name = positions[pos]
            png_path = os.path.join(rsi_dir, f"{state_name}.png")

            if not os.path.exists(png_path):
                continue

            img = Image.open(png_path).convert('RGBA')

            if merged_img is None:
                merged_img = img.copy()
                merged_entry = dict(state_map[state_name])  # Copy delays/directions
            else:
                # Alpha-over composite - handle different sizes (animated vs static)
                if merged_img.size != img.size:
                    # Use the larger canvas
                    w = max(merged_img.width, img.width)
                    h = max(merged_img.height, img.height)
                    canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                    canvas.paste(merged_img, (0, 0))
                    merged_img = canvas
                    if img.size != (w, h):
                        canvas2 = Image.new('RGBA', (w, h), (0, 0, 0, 0))
                        canvas2.paste(img, (0, 0))
                        img = canvas2
                merged_img = Image.alpha_composite(merged_img, img)

            # Mark old state for removal
            states_to_remove.add(state_name)
            files_to_remove.add(png_path)

        if merged_img is None:
            continue

        # Save merged PNG
        merged_png_path = os.path.join(rsi_dir, f"{merged_name}.png")
        merged_img.save(merged_png_path, 'PNG')

        # Create merged state entry
        merged_entry['name'] = merged_name
        new_states.append(merged_entry)

    # Remove old PNG files
    for f in files_to_remove:
        if os.path.exists(f):
            os.remove(f)

    # Update meta.json
    meta['states'] = sorted(new_states, key=lambda s: s['name'])
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"  Result: {len(new_states)} states (was {len(state_map)})")


def main():
    if len(sys.argv) < 2:
        print("Usage: python merge_rsi_orientations.py <rsi_dir> [rsi_dir2] ...")
        sys.exit(1)

    for rsi_dir in sys.argv[1:]:
        if not os.path.isdir(rsi_dir):
            print(f"Not a directory: {rsi_dir}")
            continue
        print(f"Processing {rsi_dir}...")
        merge_rsi(rsi_dir)


if __name__ == '__main__':
    main()
