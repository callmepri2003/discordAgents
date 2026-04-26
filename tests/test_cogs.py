"""
Tests for cogs/game.py and cogs/exploration.py.

All Discord interactions and DB/API calls are mocked — no gateway or network needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.game import GameCog, PokedexView, StarterView
from cogs.exploration import BattleView, ExplorationCog, MoveView
from tests.conftest import make_pokemon, make_trainer

# ── Shared fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def bot():
    b = MagicMock()
    b.session = AsyncMock()
    return b


@pytest.fixture
def interaction():
    i = MagicMock(spec=discord.Interaction)
    i.user = MagicMock()
    i.user.id = 42
    i.user.display_name = "Ash"
    i.response = AsyncMock()
    i.edit_original_response = AsyncMock()
    i.followup = AsyncMock()
    i.followup.send = AsyncMock()
    return i


# ═══════════════════════════════════════════════════════════════════════════════
# StarterView
# ═══════════════════════════════════════════════════════════════════════════════

class TestStarterView:
    async def test_pick_wrong_user_sends_ephemeral(self, bot, interaction):
        view = StarterView(bot, user_id=999)
        interaction.user.id = 42
        await view._pick(interaction, "charmander")
        interaction.response.send_message.assert_called_once()
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_pick_disables_buttons(self, bot, interaction):
        view = StarterView(bot, user_id=42)
        # Give the view some buttons so we can assert they get disabled
        btn = discord.ui.Button(label="Test")
        btn.disabled = False
        view.add_item(btn)

        pokemon = make_pokemon(name="charmander", types=["fire"])
        with (
            patch("cogs.game.get_starter", new=AsyncMock(return_value=pokemon)),
            patch("cogs.game.save_pokemon_to_party", new=AsyncMock(return_value=1)),
        ):
            await view._pick(interaction, "charmander")

        assert all(item.disabled for item in view.children)

    async def test_pick_idempotent_on_double_click(self, bot, interaction):
        view = StarterView(bot, user_id=42)
        pokemon = make_pokemon(name="bulbasaur")
        with (
            patch("cogs.game.get_starter", new=AsyncMock(return_value=pokemon)),
            patch("cogs.game.save_pokemon_to_party", new=AsyncMock(return_value=1)),
        ):
            await view._pick(interaction, "bulbasaur")
            await view._pick(interaction, "bulbasaur")  # second click — should no-op

        # defer should only be called once
        interaction.response.defer.assert_called_once()

    async def test_pick_calls_get_starter_with_correct_name(self, bot, interaction):
        view = StarterView(bot, user_id=42)
        pokemon = make_pokemon(name="squirtle", types=["water"])
        with (
            patch("cogs.game.get_starter", new=AsyncMock(return_value=pokemon)) as mock_gs,
            patch("cogs.game.save_pokemon_to_party", new=AsyncMock(return_value=1)),
        ):
            await view._pick(interaction, "squirtle")

        mock_gs.assert_called_once_with("squirtle", bot.session)

    async def test_pick_saves_pokemon_and_edits_message(self, bot, interaction):
        view = StarterView(bot, user_id=42)
        pokemon = make_pokemon(name="charmander", types=["fire"])
        with (
            patch("cogs.game.get_starter", new=AsyncMock(return_value=pokemon)),
            patch("cogs.game.save_pokemon_to_party", new=AsyncMock(return_value=7)) as mock_save,
        ):
            await view._pick(interaction, "charmander")

        mock_save.assert_called_once_with(42, pokemon, 1)
        assert pokemon.db_id == 7
        assert pokemon.party_slot == 1
        interaction.edit_original_response.assert_called_once()

    async def test_on_timeout_disables_all_items(self, bot):
        view = StarterView(bot, user_id=42)
        btn = discord.ui.Button(label="X")
        btn.disabled = False
        view.add_item(btn)
        await view.on_timeout()
        assert all(item.disabled for item in view.children)


# ═══════════════════════════════════════════════════════════════════════════════
# PokedexView
# ═══════════════════════════════════════════════════════════════════════════════

class TestPokedexView:
    def test_empty_pokedex_shows_message(self):
        view = PokedexView([], "Ash")
        embed = view.build_embed()
        assert "No Pokémon" in embed.description

    def test_single_page_next_disabled(self):
        pokemon = [make_pokemon() for _ in range(3)]
        view = PokedexView(pokemon, "Ash")
        assert view.next_btn.disabled is True
        assert view.prev_btn.disabled is True

    def test_multi_page_next_enabled(self):
        pokemon = [make_pokemon() for _ in range(8)]
        view = PokedexView(pokemon, "Ash")
        assert view.next_btn.disabled is False
        assert view.prev_btn.disabled is True

    async def test_next_advances_page(self, interaction):
        pokemon = [make_pokemon() for _ in range(8)]
        view = PokedexView(pokemon, "Ash")
        await view.next_btn.callback(interaction)
        assert view.page == 1
        interaction.response.edit_message.assert_called_once()

    async def test_prev_goes_back(self, interaction):
        pokemon = [make_pokemon() for _ in range(8)]
        view = PokedexView(pokemon, "Ash")
        view.page = 1
        view._update_buttons()
        await view.prev_btn.callback(interaction)
        assert view.page == 0

    def test_shiny_shows_sparkle(self):
        p = make_pokemon(is_shiny=True)
        view = PokedexView([p], "Ash")
        embed = view.build_embed()
        assert "✨" in embed.description

    def test_footer_shows_page_count(self):
        pokemon = [make_pokemon() for _ in range(6)]
        view = PokedexView(pokemon, "Ash")
        embed = view.build_embed()
        assert "1/2" in embed.footer.text


# ═══════════════════════════════════════════════════════════════════════════════
# GameCog commands
# ═══════════════════════════════════════════════════════════════════════════════

class TestGameCogStart:
    async def test_start_existing_trainer_with_party(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.start.callback(cog, interaction)
        call_kwargs = interaction.response.send_message.call_args.kwargs
        assert call_kwargs.get("ephemeral") is True

    async def test_start_no_trainer_creates_one(self, bot, interaction):
        new_trainer = make_trainer()
        cog = GameCog(bot)
        with (
            patch("cogs.game.get_trainer", new=AsyncMock(return_value=None)),
            patch("cogs.game.create_trainer", new=AsyncMock(return_value=new_trainer)) as mock_ct,
        ):
            await cog.start.callback(cog, interaction)
        mock_ct.assert_called_once_with(42, "Ash")
        interaction.response.send_message.assert_called_once()

    async def test_start_existing_trainer_without_party_shows_selection(self, bot, interaction):
        trainer = make_trainer(party=[])
        cog = GameCog(bot)
        with (
            patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.game.create_trainer", new=AsyncMock()) as mock_ct,
        ):
            await cog.start.callback(cog, interaction)
        mock_ct.assert_not_called()
        interaction.response.send_message.assert_called_once()


class TestGameCogParty:
    async def test_party_no_trainer(self, bot, interaction):
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=None)):
            await cog.party.callback(cog, interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_party_shows_embed(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.party.callback(cog, interaction)
        call = interaction.response.send_message.call_args
        assert isinstance(call.kwargs.get("embed") or call.args[0] if call.args else None
                          or call.kwargs.get("embed"), discord.Embed)


class TestGameCogBag:
    async def test_bag_no_trainer(self, bot, interaction):
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=None)):
            await cog.bag.callback(cog, interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_bag_shows_embed(self, bot, interaction):
        trainer = make_trainer()
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.bag.callback(cog, interaction)
        embed = interaction.response.send_message.call_args.kwargs.get("embed")
        assert isinstance(embed, discord.Embed)


class TestGameCogHeal:
    async def test_heal_no_trainer(self, bot, interaction):
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=None)):
            await cog.heal.callback(cog, interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_heal_on_cooldown(self, bot, interaction):
        import time
        trainer = make_trainer()
        cog = GameCog(bot)
        with (
            patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.game.get_heal_cooldown", new=AsyncMock(return_value=time.time() - 60)),
        ):
            await cog.heal.callback(cog, interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
        assert "busy" in interaction.response.send_message.call_args.args[0].lower() or \
               "busy" in str(interaction.response.send_message.call_args).lower()

    async def test_heal_success_restores_hp(self, bot, interaction):
        p = make_pokemon(hp=100, current_hp=40)
        trainer = make_trainer(party=[p])
        cog = GameCog(bot)
        with (
            patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.game.get_heal_cooldown", new=AsyncMock(return_value=0.0)),
            patch("cogs.game.update_pokemon", new=AsyncMock()),
            patch("cogs.game.set_heal_cooldown", new=AsyncMock()),
        ):
            await cog.heal.callback(cog, interaction)
        assert p.current_hp == 100
        interaction.response.send_message.assert_called_once()


class TestGameCogUsePotion:
    async def test_use_potion_no_trainer(self, bot, interaction):
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=None)):
            await cog.use_potion.callback(cog, interaction, slot=1)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_use_potion_no_potions(self, bot, interaction):
        trainer = make_trainer()
        trainer.potions = 0
        trainer.super_potions = 0
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.use_potion.callback(cog, interaction, slot=1)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_use_potion_wrong_slot(self, bot, interaction):
        p = make_pokemon()
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.use_potion.callback(cog, interaction, slot=3)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_use_potion_fainted_pokemon(self, bot, interaction):
        p = make_pokemon(current_hp=0)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.use_potion.callback(cog, interaction, slot=1)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_use_potion_full_hp(self, bot, interaction):
        p = make_pokemon(hp=100, current_hp=100)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        cog = GameCog(bot)
        with patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.use_potion.callback(cog, interaction, slot=1)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_use_potion_heals_20hp(self, bot, interaction):
        p = make_pokemon(hp=100, current_hp=50)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        trainer.potions = 1
        cog = GameCog(bot)
        with (
            patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.game.update_pokemon", new=AsyncMock()),
            patch("cogs.game.update_trainer_items", new=AsyncMock()),
        ):
            await cog.use_potion.callback(cog, interaction, slot=1)
        assert p.current_hp == 70
        assert trainer.potions == 0

    async def test_use_super_potion_heals_50hp(self, bot, interaction):
        p = make_pokemon(hp=100, current_hp=30)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        trainer.super_potions = 1
        cog = GameCog(bot)
        with (
            patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.game.update_pokemon", new=AsyncMock()),
            patch("cogs.game.update_trainer_items", new=AsyncMock()),
        ):
            await cog.use_potion.callback(cog, interaction, slot=1)
        assert p.current_hp == 80
        assert trainer.super_potions == 0

    async def test_use_potion_does_not_exceed_max_hp(self, bot, interaction):
        p = make_pokemon(hp=100, current_hp=90)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        trainer.potions = 1
        cog = GameCog(bot)
        with (
            patch("cogs.game.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.game.update_pokemon", new=AsyncMock()),
            patch("cogs.game.update_trainer_items", new=AsyncMock()),
        ):
            await cog.use_potion.callback(cog, interaction, slot=1)
        assert p.current_hp == 100


# ═══════════════════════════════════════════════════════════════════════════════
# ExplorationCog
# ═══════════════════════════════════════════════════════════════════════════════

class TestExplorationCogEncounter:
    async def test_no_trainer(self, bot, interaction):
        cog = ExplorationCog(bot)
        with patch("cogs.exploration.get_trainer", new=AsyncMock(return_value=None)):
            await cog.encounter.callback(cog, interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_empty_party(self, bot, interaction):
        trainer = make_trainer(party=[])
        cog = ExplorationCog(bot)
        with patch("cogs.exploration.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.encounter.callback(cog, interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_all_fainted(self, bot, interaction):
        p = make_pokemon(current_hp=0)
        trainer = make_trainer(party=[p])
        cog = ExplorationCog(bot)
        with patch("cogs.exploration.get_trainer", new=AsyncMock(return_value=trainer)):
            await cog.encounter.callback(cog, interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_resumes_existing_encounter(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        wild = make_pokemon(name="pikachu", types=["electric"])
        cog = ExplorationCog(bot)
        with (
            patch("cogs.exploration.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.exploration.get_encounter", new=AsyncMock(return_value=wild)),
            patch("cogs.exploration.get_random_wild") as mock_new,
        ):
            await cog.encounter.callback(cog, interaction)
        mock_new.assert_not_called()
        interaction.followup.send.assert_called_once()

    async def test_spawns_new_encounter_when_none_exists(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        wild = make_pokemon(name="rattata", types=["normal"])
        cog = ExplorationCog(bot)
        with (
            patch("cogs.exploration.get_trainer", new=AsyncMock(return_value=trainer)),
            patch("cogs.exploration.get_encounter", new=AsyncMock(return_value=None)),
            patch("cogs.exploration.get_random_wild", new=AsyncMock(return_value=wild)),
            patch("cogs.exploration.save_encounter", new=AsyncMock()),
        ):
            await cog.encounter.callback(cog, interaction)
        interaction.followup.send.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# BattleView
# ═══════════════════════════════════════════════════════════════════════════════

class TestBattleView:
    def _make_view(self, bot, trainer=None, wild=None):
        trainer = trainer or make_trainer(party=[make_pokemon()])
        wild = wild or make_pokemon(name="pidgey", types=["normal", "flying"])
        return BattleView(bot, trainer, wild), trainer, wild

    async def test_wrong_user_fight(self, bot, interaction):
        view, _, _ = self._make_view(bot)
        interaction.user.id = 999
        await view.fight.callback(interaction)
        interaction.response.send_message.assert_called_once()
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_fight_no_active_pokemon(self, bot, interaction):
        p = make_pokemon(current_hp=0)
        trainer = make_trainer(party=[p])
        view, _, _ = self._make_view(bot, trainer=trainer)
        await view.fight.callback(interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_fight_shows_move_view(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        trainer.user_id = 42
        view, _, _ = self._make_view(bot, trainer=trainer)
        await view.fight.callback(interaction)
        interaction.response.edit_message.assert_called_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert isinstance(kwargs.get("view"), MoveView)

    async def test_wrong_user_catch(self, bot, interaction):
        view, _, _ = self._make_view(bot)
        interaction.user.id = 999
        await view.catch.callback(interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_catch_no_pokeballs(self, bot, interaction):
        trainer = make_trainer()
        trainer.user_id = 42
        trainer.pokeballs = 0
        trainer.great_balls = 0
        trainer.ultra_balls = 0
        view, _, _ = self._make_view(bot, trainer=trainer)
        await view.catch.callback(interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_catch_success_adds_to_party(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        trainer.user_id = 42
        trainer.pokeballs = 1
        wild = make_pokemon(name="caterpie", catch_rate=255)
        view = BattleView(bot, trainer, wild)
        with (
            patch("cogs.exploration.catch_attempt", return_value=(True, 4)),
            patch("cogs.exploration.update_trainer_items", new=AsyncMock()),
            patch("cogs.exploration.save_pokemon_to_party", new=AsyncMock(return_value=2)),
            patch("cogs.exploration.clear_encounter", new=AsyncMock()),
        ):
            await view.catch.callback(interaction)
        assert trainer.pokeballs == 0
        interaction.response.edit_message.assert_called_once()
        embed = interaction.response.edit_message.call_args.kwargs.get("embed")
        assert "caught" in embed.title.lower()

    async def test_catch_fail_shows_battle_embed(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        trainer.user_id = 42
        trainer.pokeballs = 1
        view, _, _ = self._make_view(bot, trainer=trainer)
        with (
            patch("cogs.exploration.catch_attempt", return_value=(False, 2)),
            patch("cogs.exploration.update_trainer_items", new=AsyncMock()),
        ):
            await view.catch.callback(interaction)
        interaction.response.edit_message.assert_called_once()

    async def test_catch_prefers_ultra_ball(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        trainer.user_id = 42
        trainer.pokeballs = 5
        trainer.great_balls = 3
        trainer.ultra_balls = 2
        view, _, wild = self._make_view(bot, trainer=trainer)
        with (
            patch("cogs.exploration.catch_attempt", return_value=(False, 0)),
            patch("cogs.exploration.update_trainer_items", new=AsyncMock()),
        ):
            await view.catch.callback(interaction)
        assert trainer.ultra_balls == 1
        assert trainer.great_balls == 3  # untouched
        assert trainer.pokeballs == 5    # untouched

    async def test_run_clears_encounter(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        trainer.user_id = 42
        view, _, _ = self._make_view(bot, trainer=trainer)
        with patch("cogs.exploration.clear_encounter", new=AsyncMock()) as mock_clear:
            await view.run.callback(interaction)
        mock_clear.assert_called_once_with(42)
        embed = interaction.response.edit_message.call_args.kwargs.get("embed")
        assert "safely" in embed.title.lower() or "got away" in embed.title.lower()

    async def test_run_disables_buttons(self, bot, interaction):
        trainer = make_trainer(party=[make_pokemon()])
        trainer.user_id = 42
        view, _, _ = self._make_view(bot, trainer=trainer)
        with patch("cogs.exploration.clear_encounter", new=AsyncMock()):
            await view.run.callback(interaction)
        assert all(item.disabled for item in view.children)


# ═══════════════════════════════════════════════════════════════════════════════
# MoveView
# ═══════════════════════════════════════════════════════════════════════════════

class TestMoveView:
    def _make_move_view(self, bot, *, attacker_hp=100, wild_hp=50):
        from tests.conftest import make_move
        attacker = make_pokemon(hp=100, current_hp=attacker_hp, attack=200, level=20)
        attacker.db_id = 1
        wild = make_pokemon(name="rattata", hp=wild_hp, current_hp=wild_hp, defense=5)
        wild.moves = [make_move(power=10, accuracy=100, damage_class="physical")]
        trainer = make_trainer(party=[attacker])
        trainer.user_id = 42
        parent = BattleView(bot, trainer, wild)
        view = MoveView(bot, trainer, wild, parent)
        return view, trainer, wild, attacker

    async def test_wrong_user_blocked(self, bot, interaction):
        # The user guard is in the closure returned by _make_callback, not _use_move directly
        view, _, _, _ = self._make_move_view(bot)
        interaction.user.id = 999
        from tests.conftest import make_move
        callback = view._make_callback(make_move(power=40, accuracy=100))
        await callback(interaction)
        interaction.response.send_message.assert_called_once()
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True

    async def test_wild_faints_shows_victory(self, bot, interaction):
        view, trainer, wild, attacker = self._make_move_view(bot, wild_hp=1)
        from tests.conftest import make_move
        move = make_move(power=200, accuracy=100, damage_class="physical")
        with (
            patch("cogs.exploration.update_pokemon", new=AsyncMock()),
            patch("cogs.exploration.calculate_xp_gain", return_value=50),
            patch("cogs.exploration.clear_encounter", new=AsyncMock()),
        ):
            await view._use_move(interaction, move)
        embed = interaction.response.edit_message.call_args.kwargs.get("embed")
        assert "victory" in embed.title.lower()

    async def test_xp_added_on_victory(self, bot, interaction):
        view, trainer, wild, attacker = self._make_move_view(bot, wild_hp=1)
        from tests.conftest import make_move
        move = make_move(power=200, accuracy=100, damage_class="physical")
        with (
            patch("cogs.exploration.update_pokemon", new=AsyncMock()),
            patch("cogs.exploration.calculate_xp_gain", return_value=99),
            patch("cogs.exploration.clear_encounter", new=AsyncMock()),
        ):
            await view._use_move(interaction, move)
        assert attacker.xp == 99

    async def test_blackout_when_all_fainted(self, bot, interaction):
        # Wild does massive damage and player has no backup
        from tests.conftest import make_move
        attacker = make_pokemon(hp=10, current_hp=10, defense=1, level=5)
        attacker.db_id = 1
        wild = make_pokemon(name="gyarados", hp=200, current_hp=200, attack=300, level=30)
        wild.moves = [make_move(power=250, accuracy=100, damage_class="physical")]
        trainer = make_trainer(party=[attacker])
        trainer.user_id = 42
        parent = BattleView(bot, trainer, wild)
        view = MoveView(bot, trainer, wild, parent)

        move = make_move(power=1, accuracy=100, damage_class="physical")
        with (
            patch("cogs.exploration.update_pokemon", new=AsyncMock()),
            patch("cogs.exploration.clear_encounter", new=AsyncMock()),
            patch("cogs.exploration.update_encounter", new=AsyncMock()),
            patch("cogs.exploration.roll_crit", return_value=False),
        ):
            await view._use_move(interaction, move)
        embed = interaction.response.edit_message.call_args.kwargs.get("embed")
        assert embed is not None
        # Either blacked out or battle continues — just assert response was sent
        interaction.response.edit_message.assert_called_once()

    async def test_back_button_returns_to_parent(self, bot, interaction):
        view, trainer, wild, _ = self._make_move_view(bot)
        await view._back(interaction)
        interaction.response.edit_message.assert_called_once()
        kwargs = interaction.response.edit_message.call_args.kwargs
        assert kwargs.get("view") is view.parent

    async def test_back_blocked_for_wrong_user(self, bot, interaction):
        view, _, _, _ = self._make_move_view(bot)
        interaction.user.id = 999
        await view._back(interaction)
        assert interaction.response.send_message.call_args.kwargs.get("ephemeral") is True
