#!/usr/bin/env python3
"""
Apply a body stencil to marking sprites so they don't render on top of the body
when facing south.

In SS14, the Tail layer draws before the Chest/Head layers. Since sprite layers
use alpha compositing (not per-pixel z-buffer), any tail pixels that overlap
the body area will be visible. This script erases those pixels using a body
silhouette as a stencil — only for the south-facing frame.

Usage:
    python apply_body_stencil.py Resources/Textures/_Nova/Mobs/Customization/tails.rsi
    python apply_body_stencil.py Resources/Textures/_Nova/Mobs/Customization/tails.rsi --species Human
"""

import argparse
import json
import math
import os
import sys
from PIL import Image


def build_body_stencil(species_rsi: str, sprite_w: int, sprite_h: int) -> Image.Image:
    """Build a combined body silhouette from all body parts that render above the tail."""
    parts = ['torso_m', 'torso_f', 'head_m', 'head_f',
             'l_arm', 'r_arm', 'l_hand', 'r_hand',
             'l_leg', 'r_leg', 'l_foot', 'r_foot']

    stencil = Image.new('RGBA', (sprite_w, sprite_h), (0, 0, 0, 0))
    for part in parts:
        path = os.path.join(species_rsi, f'{part}.png')
        if not os.path.exists(path):
            continue
        img = Image.open(path).convert('RGBA')
        # South frame is at (0,0) in the grid
        cell = img.crop((0, 0, sprite_w, sprite_h))
        stencil = Image.alpha_composite(stencil, cell)

    return stencil


def apply_stencil_to_rsi(rsi_dir: str, stencil: Image.Image):
    """Apply body stencil to all static south-facing frames in an RSI."""
    meta_path = os.path.join(rsi_dir, 'meta.json')
    with open(meta_path) as f:
        meta = json.load(f)

    sprite_w = meta['size']['x']
    sprite_h = meta['size']['y']

    # Resize stencil if RSI has different sprite size
    if stencil.size != (sprite_w, sprite_h):
        stencil = stencil.resize((sprite_w, sprite_h), Image.NEAREST)

    stencil_pixels = list(stencil.getdata())
    stencil_mask = [p[3] > 0 for p in stencil_pixels]

    modified = 0
    for state in meta['states']:
        png_path = os.path.join(rsi_dir, f'{state["name"]}.png')
        if not os.path.exists(png_path):
            continue

        dirs = state.get('directions', 1)
        if dirs < 4:
            continue  # Only process 4-directional sprites

        has_delays = 'delays' in state and state['delays']
        frames = len(state['delays'][0]) if has_delays else 1

        img = Image.open(png_path).convert('RGBA')

        # For the RSI PNG layout, frames are read left-to-right, top-to-bottom
        # For 4 dirs: south=frame0, north=frame1, east=frame2, west=frame3
        # For animated: south_f0, south_f1, ..., north_f0, ...
        # The south direction occupies the first `frames` cells

        total_cells = dirs * frames
        cols = int(math.ceil(math.sqrt(total_cells))) if frames == 1 else frames
        if frames == 1 and dirs <= 4:
            cols = int(math.ceil(math.sqrt(dirs)))

        # South frame is always at cell index 0 (for static) or cells 0..frames-1 (animated)
        # For static 4-dir: 2x2 grid, south = (0,0)
        changed = False
        for frame_idx in range(frames):
            cell_idx = frame_idx  # South direction cells are the first `frames` cells
            col = cell_idx % cols
            row = cell_idx // cols
            x0 = col * sprite_w
            y0 = row * sprite_h

            cell = img.crop((x0, y0, x0 + sprite_w, y0 + sprite_h))
            cell_pixels = list(cell.getdata())

            new_pixels = []
            cell_changed = False
            for px, mask in zip(cell_pixels, stencil_mask):
                if mask and px[3] > 0:
                    new_pixels.append((0, 0, 0, 0))
                    cell_changed = True
                else:
                    new_pixels.append(px)

            if cell_changed:
                cell.putdata(new_pixels)
                img.paste(cell, (x0, y0))
                changed = True

        if changed:
            img.save(png_path, 'PNG')
            modified += 1

    print(f"  Stenciled {modified} sprites in {rsi_dir}")


def main():
    parser = argparse.ArgumentParser(description='Apply body stencil to marking sprites')
    parser.add_argument('rsi_dirs', nargs='+', help='RSI directories to process')
    parser.add_argument('--species-rsi', default='Resources/Textures/Mobs/Species/Human/parts.rsi',
                       help='Species body parts RSI for stencil')

    args = parser.parse_args()

    # Build stencil from species body parts
    # Use 32x32 as default, will be resized per-RSI if needed
    stencil = build_body_stencil(args.species_rsi, 32, 32)
    stencil_pixels = list(stencil.getdata())
    visible = sum(1 for p in stencil_pixels if p[3] > 0)
    print(f"Body stencil: {visible} pixels from {args.species_rsi}")

    for rsi_dir in args.rsi_dirs:
        if not os.path.isdir(rsi_dir):
            print(f"Not a directory: {rsi_dir}")
            continue
        print(f"Processing {rsi_dir}...")
        apply_stencil_to_rsi(rsi_dir, stencil)


if __name__ == '__main__':
    main()
