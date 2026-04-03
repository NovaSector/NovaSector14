using Robust.Shared.Prototypes;

namespace Content.Shared._Nova.SectorFactions;

/// <summary>
/// Defines a player-facing sector faction that gets its own station loaded at round start.
/// Separate from NpcFactionPrototype which controls AI hostility.
/// The GameMap reference is stored as a string here since GameMapPrototype is server-only.
/// </summary>
[Prototype]
public sealed partial class SectorFactionPrototype : IPrototype
{
    [IdDataField]
    public string ID { get; private set; } = default!;

    /// <summary>
    /// Localized display name of this faction.
    /// </summary>
    [DataField(required: true)]
    public LocId Name { get; private set; } = string.Empty;

    /// <summary>
    /// The ID of the GameMapPrototype to load for this faction's station.
    /// </summary>
    [DataField(required: true)]
    public string GameMap { get; private set; } = default!;

    /// <summary>
    /// IFF color for this faction's grids.
    /// </summary>
    [DataField]
    public Color Color { get; private set; } = Color.White;

    /// <summary>
    /// Whether this faction's station should be loaded at round start.
    /// </summary>
    [DataField]
    public bool Enabled { get; private set; } = true;
}
