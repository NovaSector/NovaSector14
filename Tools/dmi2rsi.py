#!/usr/bin/env python3
"""
DMI to RSI converter for porting SS13 sprites to SS14.
Converts BYOND .dmi sprite files into SS14 .rsi format (directory with meta.json + PNGs).
Optionally generates marking prototype YAML and locale FTL files.

Usage:
  python dmi2rsi.py input.dmi output_dir/ [--body-part HeadTop] [--generate-markings]
  python dmi2rsi.py input_dir/ output_dir/ --batch [--body-part HeadTop]
"""

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

from PIL import Image


def parse_dmi_metadata(filepath):
    """Parse DMI metadata from a .dmi file's zTXt Description chunk."""
    img = Image.open(filepath)
    desc = img.info.get("Description", "")
    if not desc:
        raise ValueError(f"No DMI metadata found in {filepath}")

    width = 32
    height = 32
    states = []
    current_state = None

    for line in desc.split("\n"):
        line = line.strip()
        if line.startswith("width ="):
            width = int(line.split("=")[1].strip())
        elif line.startswith("height ="):
            height = int(line.split("=")[1].strip())
        elif line.startswith("state ="):
            if current_state:
                states.append(current_state)
            name = line.split("=", 1)[1].strip().strip('"')
            current_state = {"name": name, "dirs": 1, "frames": 1, "delay": None}
        elif line.startswith("dirs =") and current_state:
            current_state["dirs"] = int(line.split("=")[1].strip())
        elif line.startswith("frames =") and current_state:
            current_state["frames"] = int(line.split("=")[1].strip())
        elif line.startswith("delay =") and current_state:
            delays = [float(d.strip()) for d in line.split("=", 1)[1].split(",")]
            current_state["delay"] = delays

    if current_state:
        states.append(current_state)

    return img, width, height, states


def extract_state_frames(img, width, height, states):
    """Extract individual frames for each state from the DMI sprite sheet."""
    img_width, img_height = img.size
    cols = img_width // width

    frames_per_state = []
    current_row = 0
    current_col = 0

    for state in states:
        total_frames = state["dirs"] * state["frames"]
        state_frames = []

        for i in range(total_frames):
            x = current_col * width
            y = current_row * height
            frame = img.crop((x, y, x + width, y + height))
            state_frames.append(frame)

            current_col += 1
            if current_col >= cols:
                current_col = 0
                current_row += 1

        frames_per_state.append(state_frames)

    return frames_per_state


def create_rsi_png(state_frames, state, width, height):
    """Create an RSI PNG for a single state.

    For multi-direction states, frames are laid out horizontally per direction.
    For animated states, all frames for each direction are concatenated horizontally.
    """
    dirs = state["dirs"]
    frames = state["frames"]

    # RSI format: single PNG with all direction frames horizontal
    # Width = frame_width * frames_per_direction
    # Height = frame_height * directions (but SS14 uses single row for non-animated)
    # Actually SS14 RSI: each state PNG has frames horizontal, directions stacked vertically
    # Wait — checking the reference: Shadekin PNGs have 4 frames horizontal (one per direction)
    # So for 4-dir, 1-frame: width = 32*4, height = 32

    png_width = width * frames
    png_height = height * dirs
    result = Image.new("RGBA", (png_width, png_height), (0, 0, 0, 0))

    for d in range(dirs):
        for f in range(frames):
            frame_idx = d * frames + f
            if frame_idx < len(state_frames):
                x = f * width
                y = d * height
                result.paste(state_frames[frame_idx], (x, y))

    return result


def generate_meta_json(states, width, height):
    """Generate RSI meta.json content."""
    meta = {
        "version": 2,
        "size": {"x": width, "y": height},
        "license": "CC-BY-SA-3.0",
        "copyright": "Ported from NovaSector SS13 (modular_nova).",
        "states": [],
    }

    for state in states:
        state_entry = {"name": state["name"], "directions": state["dirs"]}

        if state["frames"] > 1 and state["delay"]:
            # Build delay arrays per direction
            delays_per_dir = []
            frames_per = state["frames"]
            for d in range(state["dirs"]):
                dir_delays = []
                for f in range(frames_per):
                    idx = d * frames_per + f
                    if state["delay"] and idx < len(state["delay"]):
                        dir_delays.append(round(state["delay"][idx] / 10.0, 2))
                    elif state["delay"] and f < len(state["delay"]):
                        # DMI often lists delays once, not per-direction
                        dir_delays.append(round(state["delay"][f] / 10.0, 2))
                    else:
                        dir_delays.append(0.1)
                delays_per_dir.append(dir_delays)
            state_entry["delays"] = delays_per_dir

        meta["states"].append(state_entry)

    return meta


def convert_dmi_to_rsi(dmi_path, output_dir, rsi_name=None):
    """Convert a single DMI file to an RSI directory."""
    dmi_path = Path(dmi_path)
    output_dir = Path(output_dir)

    if rsi_name is None:
        rsi_name = dmi_path.stem

    rsi_dir = output_dir / f"{rsi_name}.rsi"
    rsi_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Parsing {dmi_path.name}...")
    img, width, height, states = parse_dmi_metadata(dmi_path)

    print(f"  Found {len(states)} states ({width}x{height})")
    frames_per_state = extract_state_frames(img, width, height, states)

    # Create individual PNGs for each state
    for state, state_frames in zip(states, frames_per_state):
        png = create_rsi_png(state_frames, state, width, height)
        png_path = rsi_dir / f"{state['name']}.png"
        png.save(str(png_path))

    # Generate meta.json
    meta = generate_meta_json(states, width, height)
    meta_path = rsi_dir / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"  Written to {rsi_dir}/ ({len(states)} states)")
    return states


def group_states_into_markings(states, accessory_type):
    """Group DMI states into marking definitions.

    SS13 naming conventions:
    - m_horns_simple_FRONT → marking "simple", layer FRONT
    - m_horns_antenna_fuzzballv2_FRONT_primary → marking "antenna_fuzzballv2", layer FRONT, color primary
    - m_waggingtail_fox_FRONT_primary → animated marking "fox" (wag variant)
    - cat → simple single-layer marking
    """
    markings = {}

    for state in states:
        name = state["name"]
        is_wag = False

        # Detect wagging states:
        # m_waggingtail_{name}_{LAYER}_{color} or m_tail_{name}_wagging_{LAYER}_{color}
        wag_match = re.match(
            r"m_wagging\w+?_(.+?)_(FRONT|BEHIND|ADJ)(?:_(primary|secondary|tertiary))?$",
            name,
        )
        if wag_match:
            is_wag = True
            marking_name = wag_match.group(1)
            layer = wag_match.group(2)
            color = wag_match.group(3)
        else:
            # Check for _wagging_ in the middle
            wag_match2 = re.match(
                r"m_\w+?_(.+?)_wagging_(FRONT|BEHIND|ADJ)(?:_(primary|secondary|tertiary))?$",
                name,
            )
            if wag_match2:
                is_wag = True
                marking_name = wag_match2.group(1)
                layer = wag_match2.group(2)
                color = wag_match2.group(3)
            else:
                # Standard non-wag pattern
                match = re.match(
                    r"m_\w+?_(.+?)_(FRONT|BEHIND|ADJ)(?:_(primary|secondary|tertiary))?$",
                    name,
                )
                if match:
                    marking_name = match.group(1)
                    layer = match.group(2)
                    color = match.group(3)
                else:
                    # Simple state name
                    marking_name = name
                    layer = None
                    color = None

        # Wag states get a separate marking with "Animated" suffix
        if is_wag:
            marking_name = marking_name + "_ANIMATED"

        if marking_name not in markings:
            markings[marking_name] = {"states": [], "has_layers": False, "is_animated": is_wag}

        markings[marking_name]["states"].append(
            {
                "state_name": name,
                "layer": layer,
                "color": color,
                "dirs": state["dirs"],
            }
        )
        if layer:
            markings[marking_name]["has_layers"] = True

    return markings


BODY_PART_MAP = {
    "ears": "HeadTop",
    "horns": "HeadTop",
    "tails": "Tail",
    "snouts": "Snout",
    "frills": "HeadSide",
    "wings": "Chest",
    "hair": "Hair",
    "facialhair": "FacialHair",
    "head_accessory": "HeadTop",
    "neck_accessory": "Chest",
}


def generate_marking_yaml(markings, rsi_rel_path, body_part, accessory_type):
    """Generate marking prototype YAML."""
    lines = []
    lines.append(f"# Auto-generated from {accessory_type}.dmi")
    lines.append("")

    seen_ids = set()

    for marking_name, data in sorted(markings.items()):
        is_animated = data.get("is_animated", False)

        # Create a clean ID — include accessory type to avoid cross-file collisions
        type_prefix = re.sub(r"[^a-zA-Z0-9]", "", accessory_type.title())
        if is_animated:
            base_name = marking_name.replace("_ANIMATED", "")
            clean_name = re.sub(r"[^a-zA-Z0-9]", "", base_name.title())
            marking_id = f"Nova{type_prefix}{clean_name}Animated"
        else:
            clean_name = re.sub(r"[^a-zA-Z0-9]", "", marking_name.title())
            marking_id = f"Nova{type_prefix}{clean_name}"

        # Skip duplicate IDs
        if marking_id in seen_ids:
            continue
        seen_ids.add(marking_id)

        lines.append(f"- type: marking")
        lines.append(f"  id: {marking_id}")
        lines.append(f"  bodyPart: {body_part}")
        lines.append(f"  markingCategory: {body_part}")
        if is_animated:
            lines.append(f"  speciesRestriction: []")
        lines.append(f"  sprites:")

        for state_info in data["states"]:
            lines.append(f"    - sprite: {rsi_rel_path}")
            lines.append(f"      state: {state_info['state_name']}")

        lines.append("")

    return "\n".join(lines)


def generate_locale_ftl(markings, accessory_type):
    """Generate locale FTL strings."""
    lines = []
    lines.append(f"# Auto-generated from {accessory_type}.dmi")
    lines.append("")

    seen_ids = set()

    for marking_name, data in sorted(markings.items()):
        is_animated = data.get("is_animated", False)

        type_prefix = re.sub(r"[^a-zA-Z0-9]", "", accessory_type.title())
        if is_animated:
            base_name = marking_name.replace("_ANIMATED", "")
            clean_name = re.sub(r"[^a-zA-Z0-9]", "", base_name.title())
            marking_id = f"Nova{type_prefix}{clean_name}Animated"
            display_name = base_name.replace("_", " ").title() + " (Wagging)"
        else:
            clean_name = re.sub(r"[^a-zA-Z0-9]", "", marking_name.title())
            marking_id = f"Nova{type_prefix}{clean_name}"
            display_name = marking_name.replace("_", " ").title()

        # Skip duplicate IDs
        if marking_id in seen_ids:
            continue
        seen_ids.add(marking_id)

        lines.append(f"marking-{marking_id} = {display_name}")

        for i, state_info in enumerate(data["states"]):
            # Sanitize state name: replace spaces with hyphens for FTL keys
            state_name = state_info["state_name"].replace(" ", "-")
            layer_label = state_info.get("color") or state_info.get("layer") or f"layer{i}"
            lines.append(
                f"marking-{marking_id}-{state_name} = {display_name} ({layer_label})"
            )

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert SS13 DMI sprites to SS14 RSI format"
    )
    parser.add_argument("input", help="Path to .dmi file or directory of .dmi files")
    parser.add_argument("output", help="Output directory for RSI files")
    parser.add_argument(
        "--batch", action="store_true", help="Process all .dmi files in input directory"
    )
    parser.add_argument(
        "--body-part",
        default=None,
        help="Body part for marking prototypes (HeadTop, Tail, etc.)",
    )
    parser.add_argument(
        "--generate-markings",
        action="store_true",
        help="Generate marking YAML and locale FTL files",
    )
    parser.add_argument(
        "--markings-dir",
        default=None,
        help="Output dir for marking YAML (default: output/../Prototypes)",
    )
    parser.add_argument(
        "--locale-dir",
        default=None,
        help="Output dir for locale FTL (default: output/../Locale)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.batch:
        dmi_files = sorted(input_path.glob("*.dmi"))
    else:
        dmi_files = [input_path]

    for dmi_file in dmi_files:
        print(f"\nConverting {dmi_file.name}...")
        rsi_name = dmi_file.stem
        states = convert_dmi_to_rsi(dmi_file, output_dir, rsi_name)

        if args.generate_markings:
            # Determine body part
            body_part = args.body_part
            if not body_part:
                body_part = BODY_PART_MAP.get(rsi_name, "HeadTop")

            # RSI path relative to Resources/Textures/
            rsi_rel_path = f"_Nova/Mobs/Customization/{rsi_name}.rsi"

            markings = group_states_into_markings(states, rsi_name)

            # Generate marking YAML
            yaml_content = generate_marking_yaml(
                markings, rsi_rel_path, body_part, rsi_name
            )
            markings_dir = Path(args.markings_dir) if args.markings_dir else output_dir
            markings_dir.mkdir(parents=True, exist_ok=True)
            yaml_path = markings_dir / f"nova_{rsi_name}.yml"
            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(yaml_content)
            print(f"  Markings: {yaml_path}")

            # Generate locale FTL
            ftl_content = generate_locale_ftl(markings, rsi_name)
            locale_dir = Path(args.locale_dir) if args.locale_dir else output_dir
            locale_dir.mkdir(parents=True, exist_ok=True)
            ftl_path = locale_dir / f"nova_{rsi_name}.ftl"
            with open(ftl_path, "w", encoding="utf-8") as f:
                f.write(ftl_content)
            print(f"  Locale: {ftl_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
