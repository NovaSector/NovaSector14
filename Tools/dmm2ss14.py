#!/usr/bin/env python3
"""
DMM to SS14 YAML map converter.
Converts SS13 .dmm map files into SS14 .yml map format (skeleton).
Produces floors, walls, airlocks, windows, tables, cables, and grilles.
Objects without a mapping are skipped — the result is a skeleton to build upon in-engine.

Usage: python dmm2ss14.py input.dmm output.yml [--station-id InterdyneMain]
"""

import re
import sys
import struct
import base64
import argparse
from collections import OrderedDict

# ============================================================
# SS13 turf -> SS14 tile mapping
# ============================================================
TURF_TO_TILE = {
    # Iron floors
    "/turf/open/floor/iron": "FloorSteel",
    "/turf/open/floor/iron/checker": "FloorSteelCheckerDark",
    "/turf/open/floor/iron/diagonal": "FloorSteelDiagonal",
    "/turf/open/floor/iron/herringbone": "FloorSteelHerringbone",
    "/turf/open/floor/iron/small": "FloorSteelMini",
    "/turf/open/floor/iron/textured_large": "FloorSteel",
    "/turf/open/floor/iron/freezer": "FloorFreezer",
    "/turf/open/floor/iron/kitchen": "FloorKitchen",
    "/turf/open/floor/iron/pool": "FloorSteel",
    "/turf/open/floor/iron/stairs": "FloorSteel",
    "/turf/open/floor/iron/stairs/left": "FloorSteel",
    "/turf/open/floor/iron/stairs/right": "FloorSteel",
    # Dark iron floors
    "/turf/open/floor/iron/dark": "FloorDark",
    "/turf/open/floor/iron/dark/corner": "FloorDark",
    "/turf/open/floor/iron/dark/diagonal": "FloorDarkDiagonal",
    "/turf/open/floor/iron/dark/herringbone": "FloorDarkHerringbone",
    "/turf/open/floor/iron/dark/side": "FloorDark",
    "/turf/open/floor/iron/dark/small": "FloorDarkMini",
    "/turf/open/floor/iron/dark/smooth_corner": "FloorDark",
    "/turf/open/floor/iron/dark/smooth_edge": "FloorDark",
    "/turf/open/floor/iron/dark/smooth_half": "FloorDark",
    "/turf/open/floor/iron/dark/smooth_large": "FloorDark",
    "/turf/open/floor/iron/dark/textured": "FloorDark",
    "/turf/open/floor/iron/dark/textured_half": "FloorDark",
    "/turf/open/floor/iron/dark/textured_large": "FloorDark",
    # White iron floors
    "/turf/open/floor/iron/white": "FloorWhite",
    "/turf/open/floor/iron/white/small": "FloorWhiteMini",
    "/turf/open/floor/iron/white/textured_half": "FloorWhite",
    # Wood floors
    "/turf/open/floor/wood": "FloorWood",
    "/turf/open/floor/wood/parquet": "FloorWood",
    "/turf/open/floor/wood/tile": "FloorWoodTile",
    # Special floors
    "/turf/open/floor/plating": "Plating",
    "/turf/open/floor/plating/airless": "Plating",
    "/turf/open/floor/plating/lavaland_atmos": "Plating",
    "/turf/open/floor/plating/reinforced": "FloorReinforced",
    "/turf/open/floor/circuit/telecomms": "FloorGreenCircuit",
    "/turf/open/floor/engine": "FloorReinforced",
    "/turf/open/floor/engine/bz": "FloorReinforced",
    "/turf/open/floor/engine/n2": "FloorReinforced",
    "/turf/open/floor/engine/o2": "FloorReinforced",
    "/turf/open/floor/catwalk_floor/iron_dark": "FloorDark",
    "/turf/open/floor/grass": "FloorGrass",
    # Walls (get plating underneath, wall entity placed separately)
    "/turf/closed/wall/mineral/plastitanium/nodiagonal": "Plating",
    "/turf/closed/wall/mineral/titanium/nodiagonal/shielded": "Plating",
    "/turf/closed/wall/mineral/titanium/shielded": "Plating",
    # Outdoor/lava (mapped to space for a ship)
    "/turf/closed/mineral/random/volcanic": "Space",
    "/turf/open/lava/smooth/lava_land_surface": "Space",
    "/turf/open/misc/asteroid/basalt/lava_land_surface": "Space",
    "/turf/template_noop": "Space",
}

# SS13 turf -> SS14 wall entity (for closed turfs)
TURF_TO_WALL = {
    "/turf/closed/wall/mineral/plastitanium/nodiagonal": "WallPlastitanium",
    "/turf/closed/wall/mineral/titanium/nodiagonal/shielded": "WallShuttleInterior",
    "/turf/closed/wall/mineral/titanium/shielded": "WallShuttle",
}

# ============================================================
# SS13 object -> SS14 entity mapping
# ============================================================
OBJ_TO_ENTITY = {
    # Doors
    "/obj/machinery/door/airlock": "Airlock",
    "/obj/machinery/door/airlock/engineering/glass": "AirlockEngineeringGlass",
    "/obj/machinery/door/airlock/external": "AirlockExternal",
    "/obj/machinery/door/airlock/external/glass": "AirlockExternalGlass",
    "/obj/machinery/door/airlock/freezer": "AirlockFreezer",
    "/obj/machinery/door/airlock/grunge": "Airlock",
    "/obj/machinery/door/airlock/public/glass": "AirlockGlass",
    "/obj/machinery/door/airlock/vault": "AirlockCommand",
    "/obj/machinery/door/airlock/virology": "AirlockVirology",
    "/obj/machinery/door/airlock/virology/glass": "AirlockVirologyGlass",
    "/obj/machinery/door/firedoor": "FirelockGlass",
    "/obj/machinery/door/firedoor/border_only": "FirelockEdge",
    "/obj/machinery/door/poddoor": "Firelock",
    "/obj/machinery/door/poddoor/preopen": "Firelock",
    # Windows
    "/obj/structure/window/reinforced/survival_pod/spawner/directional/east": "WindowReinforcedDirectional",
    "/obj/structure/window/reinforced/survival_pod/spawner/directional/north": "WindowReinforcedDirectional",
    "/obj/structure/window/reinforced/survival_pod/spawner/directional/south": "WindowReinforcedDirectional",
    "/obj/structure/window/reinforced/survival_pod/spawner/directional/west": "WindowReinforcedDirectional",
    "/obj/machinery/door/window/survival_pod/left/directional/east": "WindowReinforcedDirectional",
    "/obj/machinery/door/window/survival_pod/left/directional/north": "WindowReinforcedDirectional",
    "/obj/machinery/door/window/survival_pod/left/directional/south": "WindowReinforcedDirectional",
    "/obj/machinery/door/window/survival_pod/left/directional/west": "WindowReinforcedDirectional",
    "/obj/effect/spawner/structure/window/reinforced/shuttle": "ShuttleWindow",
    # Structures
    "/obj/structure/grille": "Grille",
    "/obj/structure/lattice": None,  # lattice is a tile in SS14
    "/obj/structure/cable": "CableApcExtension",
    "/obj/structure/table": "Table",
    "/obj/structure/table/wood": "TableWood",
    "/obj/structure/table/optable": "TableReinforced",
    "/obj/structure/table/reinforced": "TableReinforced",
    "/obj/structure/table/reinforced/rglass": "TableReinforcedGlass",
}

# Entities that support rotation (most SS14 entities have NoRot)
# Only these will get a rot value in the output
SUPPORTS_ROTATION = {
    # Doors
    "Airlock", "AirlockEngineeringGlass", "AirlockExternal", "AirlockExternalGlass",
    "AirlockFreezer", "AirlockGlass", "AirlockCommand", "AirlockVirology", "AirlockVirologyGlass",
    "FirelockGlass", "FirelockEdge", "Firelock",
    # Windows
    "WindowReinforcedDirectional", "ShuttleWindow", "PlasmaReinforcedWindowDirectional",
    # Conveyors / Disposal
    "ConveyorBelt", "DisposalPipe", "DisposalJunction", "DisposalJunctionFlipped",
    "DisposalYJunction", "DisposalTrunk", "DisposalUnit",
    # Shuttle
    "ThrusterUnanchored", "Railing", "RailingCorner",
    # Wall-mounted entities (need rotation to face correct wall)
    "APCBasic", "AirAlarm", "FireAlarm", "SignalButton", "SignalSwitchDirectional",
    "Poweredlight", "PoweredlightBlue", "PoweredSmallLight",
    "SurveillanceCameraGeneral", "Intercom",
    "ExtinguisherCabinetFilled", "VendingMachineWallMedical",
    "SignChem", "SignFire", "SignSmoking", "SignDirectionalEvac",
    "PosterContrabandFreeSyndicateEncryptionKey",
    "Defibrillator", "ClosetWall",
    # Atmos
    "GasVentPump", "GasVentScrubber", "GasPassiveVent", "GasPort",
    "GasPressurePump", "GasVolumePump", "GasValve", "GasMixer",
    "GasThermoMachineFreezer", "GasOutletInjector",
}

# ============================================================
# SS13 atmos -> SS14 entity mapping
# ============================================================
ATMOS_TO_ENTITY = {
    # Pipes — manifold4w = 4-way auto-connecting pipe
    # Layer 4 = supply (default layer), Layer 2 = scrubbers (Alt2)
    "/obj/machinery/atmospherics/pipe/smart/manifold4w/supply/hidden/layer4": "GasPipeFourway",
    "/obj/machinery/atmospherics/pipe/smart/manifold4w/scrubbers/hidden/layer2": "GasPipeFourwayAlt2",
    "/obj/machinery/atmospherics/pipe/layer_manifold/supply/hidden": "GasPipeFourway",
    "/obj/machinery/atmospherics/pipe/layer_manifold/scrubbers/hidden": "GasPipeFourwayAlt2",
    # Vents and scrubbers
    "/obj/machinery/atmospherics/components/unary/vent_pump/on/layer4": "GasVentPump",
    "/obj/machinery/atmospherics/components/unary/vent_scrubber/on/layer2": "GasVentScrubber",
    "/obj/machinery/atmospherics/components/unary/vent_pump/siphon/on": "GasVentPump",
    "/obj/machinery/atmospherics/components/unary/passive_vent": "GasPassiveVent",
    # Connectors
    "/obj/machinery/atmospherics/components/unary/portables_connector": "GasPort",
    "/obj/machinery/atmospherics/components/unary/portables_connector/visible": "GasPort",
    "/obj/machinery/atmospherics/components/unary/portables_connector/visible/layer4": "GasPort",
    # Binary components
    "/obj/machinery/atmospherics/components/binary/pump/on": "GasPressurePump",
    "/obj/machinery/atmospherics/components/binary/volume_pump": "GasVolumePump",
    "/obj/machinery/atmospherics/components/binary/valve/digital/layer4": "GasValve",
    # Trinary
    "/obj/machinery/atmospherics/components/trinary/mixer/airmix/flipped": "GasMixer",
    # Thermomachines
    "/obj/machinery/atmospherics/components/unary/thermomachine/freezer/on": "GasThermoMachineFreezer",
    # Outlet injector
    "/obj/machinery/atmospherics/components/unary/outlet_injector/on/layer4": "GasOutletInjector",
}

import math

# Wall-mounted entities: rotation is inverted because SS13 "directional/north"
# means "on the north wall, facing south" but SS14 rot=0 means "facing north"
WALL_MOUNTED = {
    "APCBasic", "AirAlarm", "FireAlarm", "SignalButton", "SignalSwitchDirectional",
    "Poweredlight", "PoweredlightBlue", "PoweredSmallLight",
    "SurveillanceCameraGeneral", "Intercom",
    "ExtinguisherCabinetFilled", "VendingMachineWallMedical",
    "SignChem", "SignFire", "SignSmoking", "SignDirectionalEvac",
    "PosterContrabandFreeSyndicateEncryptionKey",
    "Defibrillator", "ClosetWall",
}

# Direction mapping from SS13 dir values to SS14 rotation in radians
SS13_DIR_TO_ROT = {
    1: 0.0,                # NORTH
    2: math.pi,            # SOUTH (180°)
    4: math.pi / 2,        # EAST (90°)
    8: 3 * math.pi / 2,   # WEST (270°)
}

# Rotation for wall-mounted entities, accounting for Y-flip in coordinate conversion.
# Y-flip swaps north↔south walls, so directional/north becomes south wall in SS14.
# Wall-mounts face AWAY from the wall they're on (into the room).
SS13_DIR_TO_ROT_WALLMOUNT = {
    1: math.pi,            # on north wall → face south (pi) [Y-flipped]
    2: 0.0,                # on south wall → face north (0) [Y-flipped]
    4: 3 * math.pi / 2,   # on east wall → face west (3pi/2)
    8: math.pi / 2,        # on west wall → face east (pi/2)
}

# Directional suffix to rotation in radians (standard)
DIR_SUFFIX_TO_ROT = {
    "north": 0.0,
    "south": math.pi,
    "east": math.pi / 2,
    "west": 3 * math.pi / 2,
}

# Directional suffix to rotation in radians (wall-mounted, Y-flip compensated)
DIR_SUFFIX_TO_ROT_WALLMOUNT = {
    "north": math.pi,            # on north wall → face south [Y-flipped]
    "south": 0.0,                # on south wall → face north [Y-flipped]
    "east": 3 * math.pi / 2,    # on east wall → face west
    "west": math.pi / 2,         # on west wall → face east
}


def parse_dmm(filepath):
    """Parse a TGM-format DMM file. Returns (keys_dict, grid_data, width, height)."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse key definitions: "xx" = (\n...\n)
    keys = {}
    # Match key blocks - TGM format has one object per line
    key_pattern = re.compile(r'^"([a-zA-Z]+)" = \(\n(.*?)\)', re.MULTILINE | re.DOTALL)
    for match in key_pattern.finditer(content):
        key = match.group(1)
        block = match.group(2)
        objects = parse_key_block(block)
        keys[key] = objects

    # Parse grid data
    grid_pattern = re.compile(r'^\((\d+),(\d+),(\d+)\) = \{"\n(.*?)\n"\}', re.MULTILINE | re.DOTALL)
    columns = {}
    max_x = 0
    max_y = 0
    for match in grid_pattern.finditer(content):
        x = int(match.group(1))
        y_start = int(match.group(2))
        # z = int(match.group(3))
        col_data = match.group(4).split("\n")
        columns[x] = col_data
        max_x = max(max_x, x)
        max_y = max(max_y, len(col_data))

    return keys, columns, max_x, max_y


def parse_key_block(block):
    """Parse a key definition block into a list of (path, vars_dict) tuples."""
    objects = []
    lines = block.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip().rstrip(",")
        if not line or line.startswith("//"):
            i += 1
            continue

        # Extract the path
        path_match = re.match(r'^(/[a-zA-Z0-9_/]+)', line)
        if not path_match:
            i += 1
            continue

        path = path_match.group(1)
        var_str = line[len(path):]
        vars_dict = {}

        # Check for inline vars: /path{var = val; ...}
        if "{" in var_str:
            # Collect multi-line var block
            full_var = var_str
            while "}" not in full_var and i + 1 < len(lines):
                i += 1
                full_var += "\n" + lines[i].strip().rstrip(",")
            vars_dict = parse_vars(full_var)

        objects.append((path, vars_dict))
        i += 1

    return objects


def parse_vars(var_str):
    """Parse SS13 variable block {var = val; ...} into a dict."""
    result = {}
    # Remove braces
    var_str = var_str.strip()
    if var_str.startswith("{"):
        var_str = var_str[1:]
    if var_str.endswith("}"):
        var_str = var_str[:-1]

    # Split by semicolon or newline
    parts = re.split(r'[;\n]', var_str)
    for part in parts:
        part = part.strip().rstrip(",")
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        key = key.strip()
        val = val.strip().strip('"')
        # Try to parse as number
        try:
            if "." in val:
                result[key] = float(val)
            else:
                result[key] = int(val)
        except ValueError:
            result[key] = val
    return result


def build_tile_grid(keys, columns, width, height):
    """Build a 2D grid of (tile_name, wall_entity, objects) from DMM data."""
    grid = []  # grid[x][y]
    for x in range(1, width + 1):
        col = []
        col_keys = columns.get(x, [])
        for y_idx in range(height):
            if y_idx < len(col_keys):
                key = col_keys[y_idx]
                objects = keys.get(key, [])
            else:
                objects = []

            # Find the turf
            tile_name = "Space"
            wall_entity = None
            entities = []

            for path, vars_dict in objects:
                # Check if it's a turf
                if path.startswith("/turf/"):
                    tile_name = TURF_TO_TILE.get(path, "Plating")
                    wall_entity = TURF_TO_WALL.get(path, None)
                elif path.startswith("/area/"):
                    continue  # Skip areas
                elif path.startswith("/obj/effect/"):
                    continue  # Skip decals/effects for skeleton
                elif path.startswith("/obj/item/"):
                    continue  # Skip items for skeleton
                elif path.startswith("/obj/machinery/atmospherics/"):
                    continue  # Skip atmos — too complex for auto-conversion
                else:
                    # Try to map the object
                    entity_proto = None
                    # Try exact match first
                    if path in OBJ_TO_ENTITY:
                        entity_proto = OBJ_TO_ENTITY[path]
                    else:
                        # Try prefix match
                        for obj_path, proto in OBJ_TO_ENTITY.items():
                            if path.startswith(obj_path):
                                entity_proto = proto
                                break

                    if entity_proto:
                        # Get direction/rotation
                        is_wallmount = entity_proto in WALL_MOUNTED
                        rot = 0.0
                        if "dir" in vars_dict:
                            d = vars_dict["dir"]
                            if is_wallmount:
                                rot = SS13_DIR_TO_ROT_WALLMOUNT.get(d, 0.0)
                            else:
                                rot = SS13_DIR_TO_ROT.get(d, 0.0)
                        else:
                            # Check directional suffix
                            suffix_map = DIR_SUFFIX_TO_ROT_WALLMOUNT if is_wallmount else DIR_SUFFIX_TO_ROT
                            for suffix, r in suffix_map.items():
                                if path.endswith(f"/directional/{suffix}"):
                                    rot = r
                                    break

                        entities.append((entity_proto, rot))

                    # Check for lattice -> tile
                    if path == "/obj/structure/lattice":
                        if tile_name == "Space":
                            tile_name = "Lattice"

            col.append((tile_name, wall_entity, entities))
        grid.append(col)
    return grid


def generate_ss14_yaml(grid, width, height, station_id="InterdyneMain", grid_name="Interdyne"):
    """Generate SS14 YAML map file from processed grid."""

    # Collect all unique tile names and assign IDs
    tile_names = set()
    for col in grid:
        for tile_name, _, _ in col:
            tile_names.add(tile_name)
    tile_names.discard("Space")
    tilemap = {0: "Space"}
    for i, name in enumerate(sorted(tile_names), 1):
        tilemap[i] = name
    # Reverse lookup
    name_to_id = {v: k for k, v in tilemap.items()}

    # Build chunks (16x16)
    # SS14 coordinates: the grid is centered, we offset to put the map near origin
    # DMM Y is bottom-to-top in SS13, but in our grid array it's top-to-bottom (index 0 = y=1 in DMM)
    # SS14 Y increases upward, so we need to flip

    chunks = {}
    entities = []
    entity_uid = 2  # uid 1 is the grid entity itself

    for gx in range(width):
        for gy in range(height):
            tile_name, wall_entity, tile_entities = grid[gx][gy]

            # SS14 position: offset so map is roughly centered
            sx = gx - width // 2
            sy = (height - 1 - gy) - height // 2  # Flip Y

            # Chunk coordinates
            cx = sx // 16
            cy = sy // 16
            # Tile within chunk
            tx = sx % 16
            ty = sy % 16
            if tx < 0:
                tx += 16
                cx -= 1
            if ty < 0:
                ty += 16
                cy -= 1

            chunk_key = (cx, cy)
            if chunk_key not in chunks:
                chunks[chunk_key] = [[0] * 16 for _ in range(16)]

            tile_id = name_to_id.get(tile_name, 0)
            chunks[chunk_key][ty][tx] = tile_id

            # Add wall entity
            if wall_entity:
                entities.append({
                    "uid": entity_uid,
                    "proto": wall_entity,
                    "x": sx + 0.5,
                    "y": sy + 0.5,
                })
                entity_uid += 1

            # Add other entities
            for entity_proto, rot in tile_entities:
                ent = {
                    "uid": entity_uid,
                    "proto": entity_proto,
                    "x": sx + 0.5,
                    "y": sy + 0.5,
                }
                # Only add rotation for entities that support it
                if entity_proto in SUPPORTS_ROTATION:
                    ent["rot"] = rot
                entities.append(ent)
                entity_uid += 1

    # Encode chunks to base64
    encoded_chunks = {}
    for (cx, cy), chunk_data in chunks.items():
        # Check if chunk has any non-space tiles
        has_tiles = any(chunk_data[y][x] != 0 for y in range(16) for x in range(16))
        if not has_tiles:
            continue

        buf = bytearray()
        for y in range(16):
            for x in range(16):
                tile_id = chunk_data[y][x]
                buf += struct.pack("<i", tile_id)  # int32 LE - tile ID
                buf += struct.pack("B", 0)          # flags
                buf += struct.pack("B", 0)          # variant
                buf += struct.pack("B", 0)          # rotation/mirroring
        encoded_chunks[(cx, cy)] = base64.b64encode(bytes(buf)).decode("ascii")

    # Group entities by prototype for cleaner output
    entities_by_proto = {}
    for ent in entities:
        proto = ent["proto"]
        if proto not in entities_by_proto:
            entities_by_proto[proto] = []
        entities_by_proto[proto].append(ent)

    # Entity UIDs: 1 = map entity, 2 = grid entity, 3+ = placed objects
    # Shift all entity uids by 1 since we now have a map entity at uid 1
    for ent in entities:
        ent["uid"] += 1
    entity_uid += 1

    # Build YAML output
    lines = []
    lines.append("meta:")
    lines.append("  format: 7")
    lines.append("  category: Map")
    lines.append('  engineVersion: 267.3.0')
    lines.append('  forkId: ""')
    lines.append('  forkVersion: ""')
    lines.append(f"  entityCount: {entity_uid - 1}")
    lines.append("maps:")
    lines.append("- 1")
    lines.append("grids:")
    lines.append("- 2")
    lines.append("orphans: []")
    lines.append("nullspace: []")
    lines.append("tilemap:")
    for tid in sorted(tilemap.keys()):
        lines.append(f"  {tid}: {tilemap[tid]}")
    lines.append("entities:")

    # Map entity (uid 1)
    lines.append('- proto: ""')
    lines.append("  entities:")
    lines.append("  - uid: 1")
    lines.append("    components:")
    lines.append("    - type: MetaData")
    lines.append("    - type: Transform")
    lines.append("    - type: Map")
    lines.append("    - type: GridTree")
    lines.append("    - type: Broadphase")
    lines.append("    - type: OccluderTree")
    lines.append("    - type: Parallax")

    # Grid entity (uid 2, parented to map entity 1)
    lines.append("  - uid: 2")
    lines.append("    components:")
    lines.append("    - type: MetaData")
    lines.append(f"      name: {grid_name}")
    lines.append("    - type: Transform")
    lines.append("      parent: 1")
    lines.append("    - type: MapGrid")
    lines.append("      chunks:")

    for (cx, cy) in sorted(encoded_chunks.keys()):
        b64 = encoded_chunks[(cx, cy)]
        lines.append(f"        {cx},{cy}:")
        lines.append(f"          ind: {cx},{cy}")
        lines.append(f"          tiles: {b64}")
        lines.append(f"          version: 7")

    lines.append("    - type: Broadphase")
    lines.append("    - type: Physics")
    lines.append("      bodyStatus: InAir")
    lines.append("      angularDamping: 0.05")
    lines.append("      linearDamping: 0.05")
    lines.append("      fixedRotation: False")
    lines.append("      bodyType: Dynamic")
    lines.append("    - type: Fixtures")
    lines.append("      fixtures: {}")
    lines.append("    - type: OccluderTree")
    lines.append("    - type: SpreaderGrid")
    lines.append("    - type: Shuttle")
    lines.append("    - type: Gravity")
    lines.append("      gravityShakeSound: !type:SoundPathSpecifier")
    lines.append("        path: /Audio/Effects/alert.ogg")
    lines.append("    - type: GridPathfinding")
    lines.append("    - type: DecalGrid")
    lines.append("      chunkCollection:")
    lines.append("        version: 2")
    lines.append("        nodes: []")
    lines.append("    - type: GasTileOverlay")
    lines.append("    - type: RadiationGridResistance")
    lines.append("    - type: NavMap")
    lines.append("    - type: BecomesStation")
    lines.append(f"      id: {station_id}")

    # Grid uid for parenting entities
    grid_uid = 2

    # Entity prototypes
    for proto in sorted(entities_by_proto.keys()):
        ents = entities_by_proto[proto]
        lines.append(f"- proto: {proto}")
        lines.append("  entities:")
        for ent in ents:
            lines.append(f"  - uid: {ent['uid']}")
            lines.append("    components:")
            lines.append("    - type: Transform")
            lines.append(f"      pos: {ent['x']},{ent['y']}")
            if "rot" in ent:
                lines.append(f"      rot: {ent['rot']} rad")
            lines.append(f"      parent: {grid_uid}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Convert SS13 DMM to SS14 YAML map (skeleton)")
    parser.add_argument("input", help="Path to .dmm file")
    parser.add_argument("output", help="Path to output .yml file")
    parser.add_argument("--station-id", default="InterdyneMain", help="BecomesStation ID")
    parser.add_argument("--grid-name", default="Interdyne", help="Grid entity name")
    args = parser.parse_args()

    print(f"Parsing {args.input}...")
    keys, columns, width, height = parse_dmm(args.input)
    print(f"Map size: {width}x{height}, {len(keys)} unique tile keys")

    print("Building tile grid...")
    grid = build_tile_grid(keys, columns, width, height)

    print("Generating SS14 YAML...")
    yaml = generate_ss14_yaml(grid, width, height, args.station_id, args.grid_name)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(yaml)

    print(f"Written to {args.output}")
    print("NOTE: This is a skeleton map. You'll need to open it in the SS14 mapper to add:")
    print("  - Atmos piping (vents, scrubbers, distro)")
    print("  - Power (cables, SMES, substation, APCs, generator)")
    print("  - Shuttle components (thrusters, gyroscope, shuttle console)")
    print("  - Spawn points (SpawnPointLatejoin)")
    print("  - Machinery (specific to your station)")


if __name__ == "__main__":
    main()
