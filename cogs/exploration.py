import random

import discord
from discord import app_commands
from discord.ext import commands

from game.battle_engine import (
    calculate_hp_at_level,
    calculate_xp_gain,
    effectiveness_message,
    roll_crit,
    calculate_damage,
)
from game.catch_engine import BALL_MULTIPLIERS, catch_attempt, shake_flavour
from game.database import (
    clear_encounter,
    get_encounter,
    get_trainer,
    save_encounter,
    save_pokemon_to_party,
    update_encounter,
    update_pokemon,
    update_trainer_items,
)
from game.embeds import battle_embed, pokemon_embed
from game.models import Pokemon, Trainer
from game.pokeapi import get_random_wild


def _wild_level(trainer: Trainer) -> int:
    if not trainer.party:
        return random.randint(3, 7)
    max_lvl = max(p.level for p in trainer.party)
    spread = max(2, max_lvl // 6)
    return max(2, random.randint(max_lvl - spread, max_lvl + spread))


# ── Move selection view ───────────────────────────────────────────────────────

class MoveView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        trainer: Trainer,
        wild: Pokemon,
        parent: "BattleView",
    ) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.trainer = trainer
        self.wild = wild
        self.parent = parent

        pokemon = trainer.active_pokemon
        if pokemon:
            for move in pokemon.moves[:4]:
                label = f"{move.name}  {move.current_pp}/{move.pp} PP"
                btn = discord.ui.Button(
                    label=label, style=discord.ButtonStyle.primary, row=0
                )
                btn.callback = self._make_callback(move)
                self.add_item(btn)

        back = discord.ui.Button(
            label="← Back", style=discord.ButtonStyle.secondary, row=1
        )
        back.callback = self._back
        self.add_item(back)

    def _make_callback(self, move):
        async def callback(interaction: discord.Interaction) -> None:
            if interaction.user.id != self.trainer.user_id:
                await interaction.response.send_message(
                    "This isn't your battle!", ephemeral=True
                )
                return
            await self._use_move(interaction, move)
        return callback

    async def _back(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.trainer.user_id:
            await interaction.response.send_message(
                "This isn't your battle!", ephemeral=True
            )
            return
        embed = battle_embed(
            self.trainer.active_pokemon, self.wild,
            description="What will you do?"
        )
        await interaction.response.edit_message(embed=embed, view=self.parent)

    async def _use_move(self, interaction: discord.Interaction, move) -> None:
        attacker = self.trainer.active_pokemon
        log: list[str] = []

        # ── Player attacks ────────────────────────────────────────────────────
        move.current_pp = max(0, move.current_pp - 1)
        is_crit = roll_crit()

        if random.randint(1, 100) > move.accuracy:
            log.append(f"**{attacker.display_name}** used **{move.name}** — *but it missed!*")
        else:
            dmg, eff, _ = calculate_damage(attacker, self.wild, move, crit=is_crit)
            self.wild.current_hp = max(0, self.wild.current_hp - dmg)
            line = f"**{attacker.display_name}** used **{move.name}**! **{dmg} damage**"
            if is_crit:
                line += " ⚡ *Critical hit!*"
            log.append(line)
            eff_msg = effectiveness_message(eff)
            if eff_msg:
                log.append(f"*{eff_msg}*")

        await update_pokemon(attacker)

        # ── Wild fainted? ─────────────────────────────────────────────────────
        if self.wild.is_fainted():
            xp = calculate_xp_gain(self.wild, attacker.level)
            attacker.xp += xp
            log.append(f"\n🌟 **Wild {self.wild.display_name}** fainted!")
            log.append(f"**{attacker.display_name}** gained **{xp} XP**!")

            # Level-up loop
            xp_needed = attacker.level ** 3
            while attacker.xp >= xp_needed:
                attacker.xp -= xp_needed
                attacker.level += 1
                new_max = calculate_hp_at_level(attacker.max_hp, attacker.level)
                attacker.current_hp = min(attacker.current_hp + (new_max - attacker.max_hp), new_max)
                attacker.max_hp = new_max
                log.append(f"🎉 **{attacker.display_name}** grew to level **{attacker.level}**!")
                xp_needed = attacker.level ** 3

            await update_pokemon(attacker)
            await clear_encounter(self.trainer.user_id)
            for _item in self.parent.children:
                _item.disabled = True

            embed = discord.Embed(
                title="🏆 Victory!",
                description="\n".join(log),
                color=0xF1C40F,
            )
            if attacker.sprite_url:
                embed.set_thumbnail(url=attacker.sprite_url)
            await interaction.response.edit_message(embed=embed, view=self.parent)
            return

        # ── Wild counter-attacks ──────────────────────────────────────────────
        wild_move = random.choice(self.wild.moves)
        wild_crit = roll_crit()

        if random.randint(1, 100) <= wild_move.accuracy:
            wdmg, weff, _ = calculate_damage(self.wild, attacker, wild_move, crit=wild_crit)
            attacker.current_hp = max(0, attacker.current_hp - wdmg)
            wline = f"**Wild {self.wild.display_name}** used **{wild_move.name}**! **{wdmg} damage**"
            if wild_crit:
                wline += " ⚡ *Critical hit!*"
            log.append(wline)
            weff_msg = effectiveness_message(weff)
            if weff_msg:
                log.append(f"*{weff_msg}*")
        else:
            log.append(f"**Wild {self.wild.display_name}** used **{wild_move.name}** — *but it missed!*")

        await update_pokemon(attacker)
        await update_encounter(self.trainer.user_id, self.wild)

        # ── Player fainted? ───────────────────────────────────────────────────
        if attacker.is_fainted():
            log.append(f"\n💀 **{attacker.display_name}** fainted!")
            next_up = next(
                (p for p in self.trainer.party if not p.is_fainted() and p.db_id != attacker.db_id),
                None,
            )
            if next_up:
                log.append(f"Go, **{next_up.display_name}**!")
                self.parent.trainer = self.trainer  # refresh reference
                embed = battle_embed(next_up, self.wild, description="\n".join(log))
                await interaction.response.edit_message(embed=embed, view=self.parent)
            else:
                log.append("You have no Pokémon left...")
                log.append("**You blacked out!** 😵")
                for p in self.trainer.party:
                    p.current_hp = max(1, p.max_hp // 4)
                    await update_pokemon(p)
                await clear_encounter(self.trainer.user_id)
                for _item in self.parent.children:
                    _item.disabled = True
                embed = discord.Embed(
                    title="😵 You blacked out!",
                    description="\n".join(log)
                    + "\n\nYour Pokémon have been partially restored.",
                    color=0x2C3E50,
                )
                await interaction.response.edit_message(embed=embed, view=self.parent)
            return

        embed = battle_embed(attacker, self.wild, description="\n".join(log))
        await interaction.response.edit_message(embed=embed, view=self.parent)


# ── Main battle view ──────────────────────────────────────────────────────────

class BattleView(discord.ui.View):
    def __init__(self, bot: commands.Bot, trainer: Trainer, wild: Pokemon) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.trainer = trainer
        self.wild = wild
        self.message: discord.Message | None = None

    async def on_timeout(self) -> None:
        for _item in self.children:
            _item.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    content="⏰ Battle timed out — use `/encounter` to resume.",
                    view=self,
                )
            except discord.HTTPException:
                pass

    def _check_user(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.trainer.user_id

    @discord.ui.button(label="⚔️ Fight", style=discord.ButtonStyle.danger, row=0)
    async def fight(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self._check_user(interaction):
            await interaction.response.send_message("Not your battle!", ephemeral=True)
            return
        active = self.trainer.active_pokemon
        if not active:
            await interaction.response.send_message(
                "All your Pokémon have fainted!", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{active.display_name} — Choose a move!",
            description=active.type_display,
            color=0xE74C3C,
        )
        if active.sprite_url:
            embed.set_thumbnail(url=active.sprite_url)
        move_view = MoveView(self.bot, self.trainer, self.wild, self)
        await interaction.response.edit_message(embed=embed, view=move_view)

    @discord.ui.button(label="🎯 Catch", style=discord.ButtonStyle.success, row=0)
    async def catch(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self._check_user(interaction):
            await interaction.response.send_message("Not your battle!", ephemeral=True)
            return

        trainer = self.trainer
        if not trainer.has_pokeballs:
            await interaction.response.send_message(
                "You have no Poké Balls left! 😱", ephemeral=True
            )
            return

        # Pick best available ball
        if trainer.ultra_balls > 0:
            trainer.ultra_balls -= 1
            ball = "ultra_ball"
        elif trainer.great_balls > 0:
            trainer.great_balls -= 1
            ball = "great_ball"
        else:
            trainer.pokeballs -= 1
            ball = "pokeball"

        multiplier = BALL_MULTIPLIERS[ball]
        caught, shakes = catch_attempt(
            self.wild.catch_rate,
            self.wild.current_hp,
            self.wild.max_hp,
            ball_multiplier=multiplier,
        )
        await update_trainer_items(trainer)

        ball_display = ball.replace("_", " ").title()
        flavour = shake_flavour(shakes, caught)

        if caught:
            # Add to party if room, otherwise note it
            if len(trainer.party) < 6:
                slot = len(trainer.party) + 1
                db_id = await save_pokemon_to_party(trainer.user_id, self.wild, slot)
                self.wild.db_id = db_id
                self.wild.party_slot = slot
                trainer.party.append(self.wild)
                dest = f"added to your party in slot {slot}"
            else:
                dest = "sent to your PC box"

            await clear_encounter(trainer.user_id)
            for _item in self.children:
                _item.disabled = True

            shiny_tag = "✨ **Shiny!** " if self.wild.is_shiny else ""
            embed = pokemon_embed(
                self.wild,
                title=f"{shiny_tag}Gotcha! {self.wild.display_name} was caught!",
                description=f"{flavour}\n\n{self.wild.display_name} was {dest}! 🎉",
            )
            embed.set_footer(text=f"Used: {ball_display}")
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = battle_embed(
                trainer.active_pokemon,
                self.wild,
                description=f"Used **{ball_display}**\n{flavour}",
            )
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏃 Run", style=discord.ButtonStyle.secondary, row=0)
    async def run(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not self._check_user(interaction):
            await interaction.response.send_message("Not your battle!", ephemeral=True)
            return
        await clear_encounter(self.trainer.user_id)
        for _item in self.children:
            _item.disabled = True
        embed = discord.Embed(
            title="Got away safely!",
            description="You fled from the wild Pokémon.",
            color=0x95A5A6,
        )
        await interaction.response.edit_message(embed=embed, view=self)


# ── Cog ───────────────────────────────────────────────────────────────────────

class ExplorationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="encounter",
        description="Search the tall grass for a wild Pokémon!",
    )
    async def encounter(self, interaction: discord.Interaction) -> None:
        trainer = await get_trainer(interaction.user.id)
        if not trainer:
            await interaction.response.send_message(
                "You haven't started yet! Use `/start`.", ephemeral=True
            )
            return
        if not trainer.party:
            await interaction.response.send_message(
                "You need at least one Pokémon! Use `/start`.", ephemeral=True
            )
            return
        if not trainer.active_pokemon:
            await interaction.response.send_message(
                "All your Pokémon have fainted! Use `/heal` first.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Resume existing encounter or spawn new one
        wild = await get_encounter(interaction.user.id)
        if not wild:
            level = _wild_level(trainer)
            wild = await get_random_wild(level, self.bot.session)  # type: ignore[attr-defined]
            await save_encounter(interaction.user.id, wild)

        shiny_tag = "✨ **Shiny** " if wild.is_shiny else ""
        embed = battle_embed(
            trainer.active_pokemon,
            wild,
            description=f"A {shiny_tag}wild **{wild.display_name}** appeared! What will you do?",
        )
        view = BattleView(self.bot, trainer, wild)
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ExplorationCog(bot))
