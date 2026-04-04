#!/usr/bin/env python3
"""
DMI to RSI converter for SS13 -> SS14 sprite migration.

DMI (BYOND) format: Single PNG spritesheet with metadata in zTXt 'Description' chunk.
  Cell order per state: directions interleaved per frame
    (south_f0, north_f0, east_f0, west_f0, south_f1, north_f1, ...)

RSI (SS14) format: Directory containing meta.json + one PNG per state.
  Cell order per state: all frames per direction, directions sequential
    (south_f0, south_f1, ..., north_f0, north_f1, ..., east_f0, ..., west_f0, ...)
  PNG layout: width = num_frames * sprite_w, height = num_dirs * sprite_h

Usage:
    python dmi2rsi.py <input.dmi> <output.rsi/>
    python dmi2rsi.py <input.dmi> <output.rsi/> --prefix "nova_"
    python dmi2rsi.py <input.dmi> <output.rsi/> --filter "fox|wolf"
    python dmi2rsi.py <input.dmi> <output.rsi/> --strip-prefix "m_ears_"
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

from PIL import Image


def parse_dmi_metadata(description: str) -> tuple[dict, list[dict]]:
    """Parse DMI Description text into header info and state list."""
    lines = description.strip().split('\n')

    header = {'width': 32, 'height': 32}
    states = []
    current_state = None

    for line in lines:
        line = line.strip()
        if line.startswith('# BEGIN DMI') or line.startswith('# END DMI'):
            continue
        if line.startswith('version ='):
            continue

        if line.startswith('width ='):
            header['width'] = int(line.split('=')[1].strip())
        elif line.startswith('height ='):
            header['height'] = int(line.split('=')[1].strip())
        elif line.startswith('state ='):
            if current_state is not None:
                states.append(current_state)
            name = line.split('"')[1]
            current_state = {
                'name': name,
                'dirs': 1,
                'frames': 1,
                'delay': None,
                'rewind': False,
                'loop': 0,
                'hotspot': None,
            }
        elif current_state is not None:
            if line.startswith('dirs ='):
                current_state['dirs'] = int(line.split('=')[1].strip())
            elif line.startswith('frames ='):
                current_state['frames'] = int(line.split('=')[1].strip())
            elif line.startswith('delay ='):
                delays_str = line.split('=')[1].strip()
                current_state['delay'] = [float(d.strip()) for d in delays_str.split(',')]
            elif line.startswith('rewind ='):
                current_state['rewind'] = int(line.split('=')[1].strip()) == 1
            elif line.startswith('loop ='):
                current_state['loop'] = int(line.split('=')[1].strip())

    if current_state is not None:
        states.append(current_state)

    return header, states


def extract_dmi_cells(img: Image.Image, sprite_w: int, sprite_h: int) -> list[Image.Image]:
    """Extract all cells from a DMI spritesheet, left-to-right, top-to-bottom."""
    cols = img.width // sprite_w
    rows = img.height // sprite_h
    cells = []
    for row in range(rows):
        for col in range(cols):
            x = col * sprite_w
            y = row * sprite_h
            cell = img.crop((x, y, x + sprite_w, y + sprite_h))
            cells.append(cell)
    return cells


def dmi_to_rsi_reorder(cells: list[Image.Image], dirs: int, frames: int) -> list[Image.Image]:
    """
    Reorder cells from DMI interleaved order to RSI sequential order.

    DMI order (dirs interleaved per frame):
        dir0_f0, dir1_f0, ..., dirN_f0, dir0_f1, dir1_f1, ..., dirN_f1, ...

    RSI order (all frames per direction):
        dir0_f0, dir0_f1, ..., dir0_fN, dir1_f0, dir1_f1, ..., dir1_fN, ...
    """
    if frames == 1:
        # No reordering needed for static states
        return cells

    reordered = []
    for d in range(dirs):
        for f in range(frames):
            # DMI index: frame * dirs + dir
            idx = f * dirs + d
            if idx < len(cells):
                reordered.append(cells[idx])
    return reordered


def build_rsi_png(cells: list[Image.Image], sprite_w: int, sprite_h: int,
                  dirs: int, frames: int) -> Image.Image:
    """
    Build an RSI-format PNG from reordered cells.
    Layout: width = frames * sprite_w, height = dirs * sprite_h
    """
    if frames == 1 and dirs <= 4:
        # For static states, use a compact square-ish layout
        total = len(cells)
        cols = math.ceil(math.sqrt(total))
        rows = math.ceil(total / cols)
    else:
        cols = frames
        rows = dirs

    png = Image.new('RGBA', (cols * sprite_w, rows * sprite_h), (0, 0, 0, 0))

    for i, cell in enumerate(cells):
        col = i % cols
        row = i // cols
        png.paste(cell, (col * sprite_w, row * sprite_h))

    return png


def dmi_delay_to_rsi_delay(dmi_delay: list[float], dirs: int, frames: int) -> list[list[float]]:
    """
    Convert DMI delay (single flat list in ticks, 1 tick = 0.1s) to RSI delay format
    (list of lists, one per direction, values in seconds).

    DMI delay is a single list of per-frame delays (same for all directions).
    RSI delay is a list of lists, one per direction.
    """
    # Convert ticks to seconds
    seconds = [d * 0.1 for d in dmi_delay]
    # RSI uses the same delay list for each direction
    return [list(seconds) for _ in range(dirs)]


def sanitize_state_name(name: str) -> str:
    """Sanitize a state name for use as a filename."""
    # Replace characters that are problematic in filenames
    return name.replace('/', '_').replace('\\', '_').replace(':', '_').replace(' ', '_')


def convert_dmi_to_rsi(
    dmi_path: str,
    rsi_path: str,
    license_str: str = "CC-BY-SA-3.0",
    copyright_str: str = "",
    prefix: str = "",
    strip_prefix: str = "",
    filter_pattern: str = "",
    merge: bool = False,
):
    """Convert a DMI file to an RSI directory."""

    img = Image.open(dmi_path)
    description = img.info.get('Description', '')
    if not description:
        print(f"Error: {dmi_path} has no DMI Description metadata")
        sys.exit(1)

    header, states = parse_dmi_metadata(description)
    sprite_w = header['width']
    sprite_h = header['height']

    print(f"DMI: {dmi_path}")
    print(f"  Sprite size: {sprite_w}x{sprite_h}")
    print(f"  States: {len(states)} ({sum(1 for s in states if s['frames'] > 1)} animated)")

    # Extract all cells from the spritesheet
    all_cells = extract_dmi_cells(img, sprite_w, sprite_h)

    # Filter states if pattern provided
    if filter_pattern:
        regex = re.compile(filter_pattern, re.IGNORECASE)
        states = [s for s in states if regex.search(s['name'])]
        print(f"  After filter: {len(states)} states")

    # Create RSI directory
    os.makedirs(rsi_path, exist_ok=True)

    # Load existing meta.json if merging
    existing_states = []
    if merge and os.path.exists(os.path.join(rsi_path, 'meta.json')):
        with open(os.path.join(rsi_path, 'meta.json'), 'r') as f:
            existing_meta = json.load(f)
            existing_states = existing_meta.get('states', [])
        existing_names = {s['name'] for s in existing_states}
    else:
        existing_names = set()

    # Track cell position in the DMI spritesheet
    cell_offset = 0
    rsi_states = list(existing_states)  # Start with existing states if merging

    for state in states:
        name = state['name']
        dirs = state['dirs']
        frames = state['frames']
        total_cells = dirs * frames

        # Extract this state's cells from the spritesheet
        state_cells = all_cells[cell_offset:cell_offset + total_cells]
        cell_offset += total_cells

        if len(state_cells) < total_cells:
            print(f"  WARNING: Not enough cells for state '{name}' (expected {total_cells}, got {len(state_cells)})")
            continue

        # Apply name transformations
        output_name = sanitize_state_name(name)
        if strip_prefix and output_name.startswith(strip_prefix):
            output_name = output_name[len(strip_prefix):]
        if prefix:
            output_name = prefix + output_name

        # Skip if already exists when merging
        if output_name in existing_names:
            print(f"  SKIP (exists): {output_name}")
            continue

        # Reorder cells from DMI to RSI format
        rsi_cells = dmi_to_rsi_reorder(state_cells, dirs, frames)

        # Build the RSI PNG
        png = build_rsi_png(rsi_cells, sprite_w, sprite_h, dirs, frames)

        # Save PNG
        safe_filename = sanitize_state_name(output_name)
        png_path = os.path.join(rsi_path, f"{safe_filename}.png")
        png.save(png_path, 'PNG')

        # Build state entry for meta.json
        state_entry = {
            'name': output_name,
            'directions': dirs,
        }

        # Add delays for animated states
        if state['delay'] is not None and frames > 1:
            state_entry['delays'] = dmi_delay_to_rsi_delay(state['delay'], dirs, frames)

        rsi_states.append(state_entry)

    # Write meta.json
    meta = {
        'version': 1,
        'license': license_str,
        'copyright': copyright_str or f"Converted from {os.path.basename(dmi_path)} (NovaSector SS13)",
        'size': {
            'x': sprite_w,
            'y': sprite_h,
        },
        'states': rsi_states,
    }

    meta_path = os.path.join(rsi_path, 'meta.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"  Output: {rsi_path} ({len(rsi_states)} states)")
    return len(rsi_states)


def main():
    parser = argparse.ArgumentParser(description='Convert BYOND DMI sprites to SS14 RSI format')
    parser.add_argument('input', help='Input DMI file path')
    parser.add_argument('output', help='Output RSI directory path')
    parser.add_argument('--license', default='CC-BY-SA-3.0', help='License string for meta.json')
    parser.add_argument('--copyright', default='', help='Copyright string for meta.json')
    parser.add_argument('--prefix', default='', help='Prefix to add to all state names')
    parser.add_argument('--strip-prefix', default='', help='Prefix to strip from DMI state names')
    parser.add_argument('--filter', default='', help='Regex filter for state names')
    parser.add_argument('--merge', action='store_true', help='Merge into existing RSI (skip existing states)')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    convert_dmi_to_rsi(
        dmi_path=args.input,
        rsi_path=args.output,
        license_str=args.license,
        copyright_str=args.copyright,
        prefix=args.prefix,
        strip_prefix=args.strip_prefix,
        filter_pattern=args.filter,
        merge=args.merge,
    )


if __name__ == '__main__':
    main()
