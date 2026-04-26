import discord

from .models import TYPE_COLORS, Pokemon, Trainer


def _colour(pokemon: Pokemon) -> int:
    return TYPE_COLORS.get(pokemon.types[0], 0x5865F2)


def pokemon_embed(
    pokemon: Pokemon,
    *,
    title: str = "",
    description: str = "",
) -> discord.Embed:
    shiny_tag = "✨ " if pokemon.is_shiny else ""
    embed = discord.Embed(
        title=title or f"{shiny_tag}{pokemon.display_name}",
        description=description or pokemon.type_display,
        color=_colour(pokemon),
    )
    if pokemon.sprite_url:
        embed.set_thumbnail(url=pokemon.sprite_url)

    embed.add_field(name="Level", value=str(pokemon.level), inline=True)
    embed.add_field(
        name="HP",
        value=f"{pokemon.hp_bar()} {pokemon.current_hp}/{pokemon.max_hp}",
        inline=False,
    )
    embed.add_field(
        name="Moves",
        value="\n".join(
            f"• **{m.name}** ({m.type}) — {m.power or '—'} pwr  {m.current_pp}/{m.pp} PP"
            for m in pokemon.moves
        ) or "None",
        inline=False,
    )
    return embed


def battle_embed(
    player_pokemon: Pokemon,
    wild: Pokemon,
    *,
    description: str = "",
) -> discord.Embed:
    shiny_tag = "✨ " if wild.is_shiny else ""
    embed = discord.Embed(
        title=f"Wild {shiny_tag}{wild.display_name}  •  Lv.{wild.level}",
        description=description,
        color=_colour(wild),
    )
    if wild.sprite_url:
        embed.set_image(url=wild.sprite_url)

    embed.add_field(
        name=f"{'✨ ' if wild.is_shiny else ''}Wild {wild.display_name}  {wild.type_display}",
        value=f"{wild.hp_bar()} {wild.current_hp}/{wild.max_hp} HP",
        inline=False,
    )
    embed.add_field(
        name=f"Your {player_pokemon.display_name}  Lv.{player_pokemon.level}  {player_pokemon.type_display}",
        value=f"{player_pokemon.hp_bar()} {player_pokemon.current_hp}/{player_pokemon.max_hp} HP",
        inline=False,
    )
    return embed


def party_embed(trainer: Trainer) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎒 {trainer.username}'s Party",
        color=0x5865F2,
    )
    if not trainer.party:
        embed.description = "Your party is empty. Use `/start` to choose a starter!"
        return embed

    lines = []
    for p in trainer.party:
        status = "☠️" if p.is_fainted() else ""
        shiny = "✨" if p.is_shiny else ""
        lines.append(
            f"**{p.party_slot}.** {shiny}{p.display_name} Lv.{p.level} {p.type_display} {status}\n"
            f"   {p.hp_bar(10)} {p.current_hp}/{p.max_hp} HP"
        )
    embed.description = "\n".join(lines)
    return embed


def bag_embed(trainer: Trainer) -> discord.Embed:
    embed = discord.Embed(title=f"🎒 {trainer.username}'s Bag", color=0x9B59B6)
    embed.add_field(
        name="Poké Balls",
        value=(
            f"Poké Ball ×{trainer.pokeballs}\n"
            f"Great Ball ×{trainer.great_balls}\n"
            f"Ultra Ball ×{trainer.ultra_balls}"
        ),
        inline=True,
    )
    embed.add_field(
        name="Medicine",
        value=(
            f"Potion ×{trainer.potions}\n"
            f"Super Potion ×{trainer.super_potions}"
        ),
        inline=True,
    )
    return embed
