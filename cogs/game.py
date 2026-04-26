import time

import discord
from discord import app_commands
from discord.ext import commands

from game.database import (
    create_trainer,
    get_all_pokemon,
    get_heal_cooldown,
    get_trainer,
    save_pokemon_to_party,
    set_heal_cooldown,
    update_pokemon,
    update_trainer_items,
)
from game.embeds import bag_embed, party_embed, pokemon_embed
from game.models import TYPE_EMOJI
from game.pokeapi import get_starter

HEAL_COOLDOWN_SECS = 1800  # 30 minutes


class StarterView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: int) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.user_id = user_id
        self.chosen = False

    async def _pick(self, interaction: discord.Interaction, name: str) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your starter selection!", ephemeral=True
            )
            return
        if self.chosen:
            return
        self.chosen = True
        self.disable_all_items()

        await interaction.response.defer()
        pokemon = await get_starter(name, self.bot.session)  # type: ignore[attr-defined]
        db_id = await save_pokemon_to_party(self.user_id, pokemon, 1)
        pokemon.db_id = db_id
        pokemon.party_slot = 1

        embed = pokemon_embed(
            pokemon,
            title=f"{'✨ ' if pokemon.is_shiny else ''}You chose {pokemon.display_name}!",
            description=f"{pokemon.type_display}\nGood luck on your journey, trainer!",
        )
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🌿 Bulbasaur", style=discord.ButtonStyle.success)
    async def bulbasaur(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._pick(i, "bulbasaur")

    @discord.ui.button(label="🔥 Charmander", style=discord.ButtonStyle.danger)
    async def charmander(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._pick(i, "charmander")

    @discord.ui.button(label="💧 Squirtle", style=discord.ButtonStyle.primary)
    async def squirtle(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._pick(i, "squirtle")

    async def on_timeout(self) -> None:
        self.disable_all_items()


class PokedexView(discord.ui.View):
    """Paginated Pokédex."""

    PAGE_SIZE = 5

    def __init__(self, pokemon_list: list, trainer_name: str) -> None:
        super().__init__(timeout=120)
        self.pages = [
            pokemon_list[i : i + self.PAGE_SIZE]
            for i in range(0, max(1, len(pokemon_list)), self.PAGE_SIZE)
        ]
        self.page = 0
        self.trainer_name = trainer_name
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= len(self.pages) - 1

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"📖 {self.trainer_name}'s Pokédex",
            color=0xE74C3C,
        )
        chunk = self.pages[self.page] if self.pages else []
        if not chunk:
            embed.description = "No Pokémon caught yet!"
            return embed
        lines = []
        for p in chunk:
            shiny = "✨" if p.is_shiny else ""
            types = " / ".join(
                f"{TYPE_EMOJI.get(t, '')} {t.capitalize()}" for t in p.types
            )
            lines.append(
                f"**#{p.id}  {shiny}{p.display_name}**  Lv.{p.level}  {types}"
            )
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Page {self.page + 1}/{len(self.pages)}")
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        self.page -= 1
        self._update_buttons()
        await i.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        self.page += 1
        self._update_buttons()
        await i.response.edit_message(embed=self.build_embed(), view=self)


class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /start ────────────────────────────────────────────────────────────────

    @app_commands.command(name="start", description="Begin your Pokémon journey!")
    async def start(self, interaction: discord.Interaction) -> None:
        trainer = await get_trainer(interaction.user.id)
        if trainer and trainer.party:
            await interaction.response.send_message(
                "You already have a starter! Use `/party` to see your team.", ephemeral=True
            )
            return

        if not trainer:
            trainer = await create_trainer(interaction.user.id, interaction.user.display_name)

        embed = discord.Embed(
            title="Welcome to the world of Pokémon!",
            description=(
                "Professor Oak needs your help filling the Pokédex.\n\n"
                "Choose your **starter Pokémon**:"
            ),
            color=0x27AE60,
        )
        embed.add_field(
            name="🌿 Bulbasaur — Grass / Poison",
            value="Sturdy and great for beginners!",
            inline=False,
        )
        embed.add_field(
            name="🔥 Charmander — Fire",
            value="High attack; rewards bold play!",
            inline=False,
        )
        embed.add_field(
            name="💧 Squirtle — Water",
            value="Well-rounded defensive pick!",
            inline=False,
        )
        view = StarterView(self.bot, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    # ── /party ────────────────────────────────────────────────────────────────

    @app_commands.command(name="party", description="View your party Pokémon.")
    async def party(self, interaction: discord.Interaction) -> None:
        trainer = await get_trainer(interaction.user.id)
        if not trainer:
            await interaction.response.send_message(
                "You haven't started yet! Use `/start`.", ephemeral=True
            )
            return
        await interaction.response.send_message(embed=party_embed(trainer))

    # ── /bag ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="bag", description="Check your items.")
    async def bag(self, interaction: discord.Interaction) -> None:
        trainer = await get_trainer(interaction.user.id)
        if not trainer:
            await interaction.response.send_message(
                "You haven't started yet! Use `/start`.", ephemeral=True
            )
            return
        await interaction.response.send_message(embed=bag_embed(trainer))

    # ── /heal ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="heal", description="Heal your Pokémon at the Pokémon Center.")
    async def heal(self, interaction: discord.Interaction) -> None:
        trainer = await get_trainer(interaction.user.id)
        if not trainer:
            await interaction.response.send_message(
                "You haven't started yet! Use `/start`.", ephemeral=True
            )
            return

        now = time.time()
        last = await get_heal_cooldown(interaction.user.id)
        remaining = HEAL_COOLDOWN_SECS - (now - last)
        if remaining > 0:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            await interaction.response.send_message(
                f"⏳ The Pokémon Center is busy! Come back in **{mins}m {secs}s**.",
                ephemeral=True,
            )
            return

        for p in trainer.party:
            p.current_hp = p.max_hp
            await update_pokemon(p)

        await set_heal_cooldown(interaction.user.id, now)

        embed = discord.Embed(
            title="🏥 Pokémon Center",
            description="Your Pokémon have been fully healed! ❤️",
            color=0xE91E63,
        )
        await interaction.response.send_message(embed=embed)

    # ── /pokedex ──────────────────────────────────────────────────────────────

    @app_commands.command(name="pokedex", description="Browse all your caught Pokémon.")
    async def pokedex(self, interaction: discord.Interaction) -> None:
        trainer = await get_trainer(interaction.user.id)
        if not trainer:
            await interaction.response.send_message(
                "You haven't started yet! Use `/start`.", ephemeral=True
            )
            return

        all_pokemon = await get_all_pokemon(interaction.user.id)
        view = PokedexView(all_pokemon, trainer.username)
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    # ── /use_potion ───────────────────────────────────────────────────────────

    @app_commands.command(name="use_potion", description="Use a Potion on a party Pokémon.")
    @app_commands.describe(slot="Party slot (1–6)")
    async def use_potion(self, interaction: discord.Interaction, slot: int) -> None:
        trainer = await get_trainer(interaction.user.id)
        if not trainer:
            await interaction.response.send_message("Use `/start` first!", ephemeral=True)
            return

        if trainer.potions <= 0 and trainer.super_potions <= 0:
            await interaction.response.send_message("You have no Potions!", ephemeral=True)
            return

        target = next((p for p in trainer.party if p.party_slot == slot), None)
        if not target:
            await interaction.response.send_message(
                f"No Pokémon in slot {slot}.", ephemeral=True
            )
            return
        if target.is_fainted():
            await interaction.response.send_message(
                f"{target.display_name} has fainted and can't be healed this way.", ephemeral=True
            )
            return
        if target.current_hp == target.max_hp:
            await interaction.response.send_message(
                f"{target.display_name} is already at full HP!", ephemeral=True
            )
            return

        if trainer.super_potions > 0:
            heal = 50
            trainer.super_potions -= 1
            item = "Super Potion"
        else:
            heal = 20
            trainer.potions -= 1
            item = "Potion"

        target.current_hp = min(target.max_hp, target.current_hp + heal)
        await update_pokemon(target)
        await update_trainer_items(trainer)

        embed = discord.Embed(
            title=f"🧪 Used {item}!",
            description=(
                f"**{target.display_name}** recovered **{heal} HP**!\n"
                f"{target.hp_bar()} {target.current_hp}/{target.max_hp} HP"
            ),
            color=0x2ECC71,
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GameCog(bot))
