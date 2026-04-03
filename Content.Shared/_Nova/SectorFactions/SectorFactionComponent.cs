using Robust.Shared.GameStates;
using Robust.Shared.Prototypes;

namespace Content.Shared._Nova.SectorFactions;

/// <summary>
/// Marks a station entity as belonging to a sector faction.
/// Added to station entity prototypes to identify which faction owns this station.
/// </summary>
[RegisterComponent, NetworkedComponent]
public sealed partial class SectorFactionComponent : Component
{
    /// <summary>
    /// The sector faction this station belongs to.
    /// </summary>
    [DataField(required: true)]
    public ProtoId<SectorFactionPrototype> Faction = default!;
}
