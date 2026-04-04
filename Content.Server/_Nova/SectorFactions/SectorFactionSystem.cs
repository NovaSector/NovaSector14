using Content.Server.GameTicking;
using Content.Server.GameTicking.Events;
using Content.Server.Maps;
using Content.Shared._Nova.SectorFactions;
using Robust.Shared.Map;
using Robust.Shared.Prototypes;

namespace Content.Server._Nova.SectorFactions;

/// <summary>
/// Injects faction station maps at round start via LoadingMapsEvent.
/// Each enabled SectorFactionPrototype gets its GameMap loaded alongside the main station.
/// Also ensures faction maps get properly initialized (MapInit + unpause),
/// since the game ticker only initializes the default/first map.
/// </summary>
public sealed class SectorFactionSystem : EntitySystem
{
    [Dependency] private readonly IPrototypeManager _proto = default!;
    [Dependency] private readonly SharedMapSystem _mapSystem = default!;

    /// <summary>
    /// Map IDs loaded by faction maps that need initialization.
    /// </summary>
    private readonly List<MapId> _pendingFactionMaps = new();

    public override void Initialize()
    {
        base.Initialize();
        SubscribeLocalEvent<LoadingMapsEvent>(OnLoadingMaps);
        SubscribeLocalEvent<PostGameMapLoad>(OnPostGameMapLoad);
        SubscribeLocalEvent<RoundStartingEvent>(OnRoundStarting);
    }

    private void OnLoadingMaps(LoadingMapsEvent ev)
    {
        _pendingFactionMaps.Clear();

        foreach (var faction in _proto.EnumeratePrototypes<SectorFactionPrototype>())
        {
            if (!faction.Enabled)
                continue;

            if (!_proto.TryIndex<GameMapPrototype>(faction.GameMap, out var gameMap))
            {
                Log.Warning($"Sector faction '{faction.ID}' references unknown game map '{faction.GameMap}'");
                continue;
            }

            ev.Maps.Add(gameMap);
            Log.Info($"Sector faction '{faction.ID}' added map '{gameMap.MapName}' to round loading");
        }
    }

    private void OnPostGameMapLoad(PostGameMapLoad ev)
    {
        // Check if this map belongs to a faction
        foreach (var faction in _proto.EnumeratePrototypes<SectorFactionPrototype>())
        {
            if (!faction.Enabled)
                continue;

            if (faction.GameMap == ev.GameMap.ID)
            {
                _pendingFactionMaps.Add(ev.Map);
                Log.Info($"Sector faction '{faction.ID}' map loaded on MapId {ev.Map}");
                break;
            }
        }
    }

    private void OnRoundStarting(RoundStartingEvent ev)
    {
        // Initialize faction maps that the game ticker skipped
        // (it only initializes DefaultMap / maps[0])
        foreach (var mapId in _pendingFactionMaps)
        {
            if (_mapSystem.IsInitialized(mapId))
                continue;

            _mapSystem.InitializeMap(mapId);
            Log.Info($"Initialized faction map on MapId {mapId}");
        }

        _pendingFactionMaps.Clear();
    }
}
