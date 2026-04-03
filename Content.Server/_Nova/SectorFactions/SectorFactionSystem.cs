using Content.Server.GameTicking;
using Content.Server.Maps;
using Content.Shared._Nova.SectorFactions;
using Robust.Shared.Prototypes;

namespace Content.Server._Nova.SectorFactions;

/// <summary>
/// Injects faction station maps at round start via LoadingMapsEvent.
/// Each enabled SectorFactionPrototype gets its GameMap loaded alongside the main station.
/// </summary>
public sealed class SectorFactionSystem : EntitySystem
{
    [Dependency] private readonly IPrototypeManager _proto = default!;

    public override void Initialize()
    {
        base.Initialize();
        SubscribeLocalEvent<LoadingMapsEvent>(OnLoadingMaps);
    }

    private void OnLoadingMaps(LoadingMapsEvent ev)
    {
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
}
