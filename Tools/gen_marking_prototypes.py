#!/usr/bin/env python3
"""
Generate SS14 marking prototype YAML files from RSI meta.json state data.

Analyzes state naming patterns from converted SS13 DMI files:
  - Base name: fox, bunny, bigwolf, etc.
  - Position: _FRONT (over body), _ADJ (behind body), _BEHIND
  - Color layer: _primary, _secondary, _tertiary (or none for single-color)

In SS14, each RSI state already contains 4-directional frames, so FRONT/BEHIND
are redundant. We pick one orientation per base name (preferring BEHIND/ADJ over
FRONT, since tails/ears render behind the body by default).

Usage:
    python gen_marking_prototypes.py ears  --rsi _Nova/Mobs/Customization/ears.rsi --body-part HeadTop --category HeadTop
    python gen_marking_prototypes.py tails --rsi _Nova/Mobs/Customization/tails.rsi --body-part Tail --category Tail
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict


# Color layer order for sprite ordering
COLOR_ORDER = ['primary', 'secondary', 'tertiary']

# Position preference order: prefer BEHIND/ADJ (renders behind body) since
# SS14 handles directionality within each state's 4-direction frames.
POSITION_PREFERENCE = ['BEHIND', 'ADJ', 'FRONT', 'NONE']


def parse_states(meta_path: str) -> list[dict]:
    """Load states from RSI meta.json."""
    with open(meta_path, 'r') as f:
        data = json.load(f)
    return data.get('states', [])


def group_states(states: list[dict]) -> dict:
    """
    Group states by base_name -> {position: {color_layer: state_name}}.

    Handles these patterns:
      fox_FRONT_primary -> base=fox, pos=FRONT, color=primary
      fox_ADJ_secondary -> base=fox, pos=ADJ, color=secondary
      bear_FRONT        -> base=bear, pos=FRONT, color=none (single-color)
    """
    groups = defaultdict(lambda: defaultdict(dict))

    for state in states:
        name = state['name']

        # Try to match color layer suffix
        color_match = re.match(r'^(.+)_(primary|secondary|tertiary)$', name)
        if color_match:
            rest = color_match.group(1)
            color = color_match.group(2)
        else:
            rest = name
            color = 'none'

        # Try to match position suffix
        pos_match = re.match(r'^(.+)_(FRONT|ADJ|BEHIND)$', rest)
        if pos_match:
            base = pos_match.group(1)
            position = pos_match.group(2)
        else:
            base = rest
            position = 'NONE'

        groups[base][position][color] = name

    return dict(groups)


def pick_best_position(positions: dict) -> str:
    """Pick the best position variant for a marking (prefer BEHIND/ADJ)."""
    for pos in POSITION_PREFERENCE:
        if pos in positions:
            return pos
    return list(positions.keys())[0]


def generate_marking_id(prefix: str, base_name: str) -> str:
    """Generate a marking prototype ID from base name."""
    parts = base_name.replace('_', ' ').split()
    pascal = ''.join(p.capitalize() for p in parts)
    return f"{prefix}{pascal}"


def generate_yaml(
    groups: dict,
    rsi_path: str,
    body_part: str,
    category: str,
    id_prefix: str,
    species_restriction: list[str] | None = None,
) -> str:
    """Generate YAML marking prototypes from grouped states."""
    lines = []

    for base_name in sorted(groups.keys()):
        positions = groups[base_name]
        marking_id = generate_marking_id(id_prefix, base_name)

        # Pick the best single orientation
        best_pos = pick_best_position(positions)
        color_layers = positions[best_pos]

        lines.append(f"- type: marking")
        lines.append(f"  id: {marking_id}")
        lines.append(f"  bodyPart: {body_part}")
        lines.append(f"  markingCategory: {category}")

        if species_restriction:
            lines.append(f"  speciesRestriction: [{', '.join(species_restriction)}]")

        lines.append(f"  sprites:")

        if 'none' in color_layers:
            # Single-color layer
            state = color_layers['none']
            lines.append(f"  - sprite: {rsi_path}")
            lines.append(f"    state: {state}")
        else:
            # Multi-color layers in order
            for color in COLOR_ORDER:
                if color in color_layers:
                    state = color_layers[color]
                    lines.append(f"  - sprite: {rsi_path}")
                    lines.append(f"    state: {state}")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Generate marking prototype YAML from RSI meta.json')
    parser.add_argument('name', help='Output file name (e.g., ears, tails)')
    parser.add_argument('--rsi', required=True, help='RSI path relative to Textures/ (e.g., _Nova/Mobs/Customization/ears.rsi)')
    parser.add_argument('--body-part', required=True, help='HumanoidVisualLayers body part (e.g., HeadTop, Tail, Snout)')
    parser.add_argument('--category', required=True, help='MarkingCategory (e.g., HeadTop, Tail, Snout)')
    parser.add_argument('--prefix', default='Nova', help='ID prefix for marking prototypes')
    parser.add_argument('--species', default=None, help='Comma-separated species restriction list')
    parser.add_argument('--output-dir', default='Resources/Prototypes/_Nova/Entities/Mobs/Customization/Markings',
                       help='Output directory')
    parser.add_argument('--exclude', default='', help='Regex pattern to exclude states')

    args = parser.parse_args()

    # Find meta.json
    meta_path = os.path.join('Resources', 'Textures', args.rsi, 'meta.json')
    if not os.path.exists(meta_path):
        print(f"Error: {meta_path} not found")
        sys.exit(1)

    states = parse_states(meta_path)

    if args.exclude:
        exclude_re = re.compile(args.exclude, re.IGNORECASE)
        states = [s for s in states if not exclude_re.search(s['name'])]

    groups = group_states(states)

    species = args.species.split(',') if args.species else None

    yaml = generate_yaml(
        groups=groups,
        rsi_path=args.rsi,
        body_part=args.body_part,
        category=args.category,
        id_prefix=args.prefix,
        species_restriction=species,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, f"nova_{args.name}.yml")
    with open(output_path, 'w') as f:
        f.write(yaml)

    num_markings = yaml.count('- type: marking')
    print(f"Generated {num_markings} marking prototypes -> {output_path}")


if __name__ == '__main__':
    main()
