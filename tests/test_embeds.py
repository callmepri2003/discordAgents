"""
Tests for game/embeds.py.
discord.Embed is a plain data object — no gateway connection needed.
"""
import discord

from game.embeds import bag_embed, battle_embed, party_embed, pokemon_embed
from game.models import TYPE_COLORS
from tests.conftest import make_move, make_pokemon, make_trainer


# ── pokemon_embed ─────────────────────────────────────────────────────────────

class TestPokemonEmbed:
    def test_title_defaults_to_display_name(self):
        p = make_pokemon(name="pikachu", types=["electric"])
        embed = pokemon_embed(p)
        assert "Pikachu" in embed.title

    def test_custom_title_overrides(self):
        p = make_pokemon(name="pikachu")
        embed = pokemon_embed(p, title="Wild Encounter!")
        assert embed.title == "Wild Encounter!"

    def test_shiny_tag_in_title(self):
        p = make_pokemon(name="pikachu", is_shiny=True)
        embed = pokemon_embed(p)
        assert "✨" in embed.title

    def test_no_shiny_tag_when_not_shiny(self):
        p = make_pokemon(name="pikachu", is_shiny=False)
        embed = pokemon_embed(p)
        assert "✨" not in embed.title

    def test_description_is_type_display_by_default(self):
        p = make_pokemon(types=["fire"])
        embed = pokemon_embed(p)
        assert "Fire" in embed.description

    def test_custom_description_overrides(self):
        p = make_pokemon(name="pikachu")
        embed = pokemon_embed(p, description="A wild Pikachu appeared!")
        assert embed.description == "A wild Pikachu appeared!"

    def test_colour_matches_primary_type(self):
        p = make_pokemon(types=["fire"])
        embed = pokemon_embed(p)
        assert embed.colour.value == TYPE_COLORS["fire"]

    def test_thumbnail_set_when_sprite_url(self):
        p = make_pokemon()
        p.sprite_url = "https://example.com/sprite.png"
        embed = pokemon_embed(p)
        assert embed.thumbnail.url == "https://example.com/sprite.png"

    def test_no_thumbnail_when_empty_sprite_url(self):
        """When sprite_url is empty, thumbnail url should not be set."""
        p = make_pokemon()
        p.sprite_url = ""
        embed = pokemon_embed(p)
        # discord.Embed.thumbnail is an EmbedProxy; url is None when not set
        assert embed.thumbnail.url is None

    def test_level_field_present(self):
        p = make_pokemon(level=15)
        embed = pokemon_embed(p)
        field_names = [f.name for f in embed.fields]
        assert "Level" in field_names

    def test_level_field_value(self):
        p = make_pokemon(level=42)
        embed = pokemon_embed(p)
        level_field = next(f for f in embed.fields if f.name == "Level")
        assert level_field.value == "42"

    def test_hp_field_present(self):
        p = make_pokemon(hp=100, current_hp=75)
        embed = pokemon_embed(p)
        field_names = [f.name for f in embed.fields]
        assert "HP" in field_names

    def test_hp_field_contains_hp_values(self):
        p = make_pokemon(hp=100, current_hp=75)
        embed = pokemon_embed(p)
        hp_field = next(f for f in embed.fields if f.name == "HP")
        assert "75" in hp_field.value
        assert "100" in hp_field.value

    def test_moves_field_present(self):
        p = make_pokemon()
        embed = pokemon_embed(p)
        field_names = [f.name for f in embed.fields]
        assert "Moves" in field_names

    def test_moves_field_shows_move_names(self):
        moves = [make_move(name="Flamethrower", type_="fire", power=90, damage_class="special")]
        p = make_pokemon(moves=moves)
        embed = pokemon_embed(p)
        moves_field = next(f for f in embed.fields if f.name == "Moves")
        assert "Flamethrower" in moves_field.value

    def test_moves_field_no_moves(self):
        """When pokemon has no moves field should say None."""
        p = make_pokemon(moves=[])
        embed = pokemon_embed(p)
        moves_field = next(f for f in embed.fields if f.name == "Moves")
        assert moves_field.value == "None"

    def test_nickname_used_in_title(self):
        p = make_pokemon(name="pikachu", nickname="Sparky")
        embed = pokemon_embed(p)
        assert "Sparky" in embed.title

    def test_returns_discord_embed(self):
        p = make_pokemon()
        embed = pokemon_embed(p)
        assert isinstance(embed, discord.Embed)

    def test_unknown_type_uses_default_colour(self):
        p = make_pokemon(types=["shadow"])  # not in TYPE_COLORS
        embed = pokemon_embed(p)
        assert embed.colour.value == 0x5865F2


# ── battle_embed ──────────────────────────────────────────────────────────────

class TestBattleEmbed:
    def test_title_contains_wild_pokemon_name(self):
        player = make_pokemon(name="pikachu", types=["electric"])
        wild = make_pokemon(name="rattata", types=["normal"], level=5)
        embed = battle_embed(player, wild)
        assert "Rattata" in embed.title

    def test_title_contains_level(self):
        player = make_pokemon(name="pikachu")
        wild = make_pokemon(name="rattata", level=8)
        embed = battle_embed(player, wild)
        assert "8" in embed.title

    def test_shiny_tag_in_title_for_shiny_wild(self):
        player = make_pokemon(name="pikachu")
        wild = make_pokemon(name="rattata", is_shiny=True)
        embed = battle_embed(player, wild)
        assert "✨" in embed.title

    def test_no_shiny_tag_for_normal_wild(self):
        player = make_pokemon(name="pikachu")
        wild = make_pokemon(name="rattata", is_shiny=False)
        embed = battle_embed(player, wild)
        assert "✨" not in embed.title

    def test_colour_based_on_wild_type(self):
        player = make_pokemon(name="pikachu", types=["electric"])
        wild = make_pokemon(name="charmander", types=["fire"])
        embed = battle_embed(player, wild)
        assert embed.colour.value == TYPE_COLORS["fire"]

    def test_image_set_to_wild_sprite(self):
        player = make_pokemon(name="pikachu")
        wild = make_pokemon(name="rattata")
        wild.sprite_url = "https://example.com/rattata.png"
        embed = battle_embed(player, wild)
        assert embed.image.url == "https://example.com/rattata.png"

    def test_no_image_when_no_sprite(self):
        """When sprite_url is empty, image url should not be set."""
        player = make_pokemon(name="pikachu")
        wild = make_pokemon(name="rattata")
        wild.sprite_url = ""
        embed = battle_embed(player, wild)
        # discord.Embed.image is an EmbedProxy; url is None when not set
        assert embed.image.url is None

    def test_two_fields_present(self):
        player = make_pokemon(name="pikachu", types=["electric"])
        wild = make_pokemon(name="rattata", types=["normal"])
        embed = battle_embed(player, wild)
        assert len(embed.fields) == 2

    def test_wild_field_contains_hp(self):
        player = make_pokemon(name="pikachu")
        wild = make_pokemon(name="rattata", hp=60, current_hp=45)
        embed = battle_embed(player, wild)
        wild_field = embed.fields[0]
        assert "45" in wild_field.value
        assert "60" in wild_field.value

    def test_player_field_contains_hp(self):
        player = make_pokemon(name="pikachu", hp=100, current_hp=80)
        wild = make_pokemon(name="rattata")
        embed = battle_embed(player, wild)
        player_field = embed.fields[1]
        assert "80" in player_field.value
        assert "100" in player_field.value

    def test_description_passed_through(self):
        player = make_pokemon(name="pikachu")
        wild = make_pokemon(name="rattata")
        embed = battle_embed(player, wild, description="Go!")
        assert embed.description == "Go!"

    def test_returns_discord_embed(self):
        player = make_pokemon()
        wild = make_pokemon()
        embed = battle_embed(player, wild)
        assert isinstance(embed, discord.Embed)


# ── party_embed ───────────────────────────────────────────────────────────────

class TestPartyEmbed:
    def test_title_contains_username(self):
        trainer = make_trainer()
        embed = party_embed(trainer)
        assert "Ash" in embed.title

    def test_empty_party_description(self):
        trainer = make_trainer(party=[])
        embed = party_embed(trainer)
        assert "empty" in embed.description.lower() or "/start" in embed.description

    def test_party_with_one_pokemon(self):
        p = make_pokemon(name="pikachu")
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        embed = party_embed(trainer)
        assert "Pikachu" in embed.description

    def test_party_shows_level(self):
        p = make_pokemon(name="pikachu", level=25)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        embed = party_embed(trainer)
        assert "25" in embed.description

    def test_fainted_pokemon_shows_skull(self):
        p = make_pokemon(name="pikachu", hp=100, current_hp=0)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        embed = party_embed(trainer)
        assert "☠️" in embed.description

    def test_shiny_pokemon_shows_sparkle(self):
        p = make_pokemon(name="pikachu", is_shiny=True)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        embed = party_embed(trainer)
        assert "✨" in embed.description

    def test_non_shiny_no_sparkle(self):
        p = make_pokemon(name="pikachu", is_shiny=False)
        p.party_slot = 1
        trainer = make_trainer(party=[p])
        embed = party_embed(trainer)
        # Description should not contain the shiny sparkle emoji
        lines = embed.description.split("\n")
        pikachu_line = next(line for line in lines if "Pikachu" in line)
        assert "✨" not in pikachu_line

    def test_party_with_six_pokemon(self):
        """A full party of 6 should all appear in the embed."""
        names = ["bulbasaur", "charmander", "squirtle", "pikachu", "mewtwo", "mew"]
        types_map = {
            "bulbasaur": ["grass", "poison"], "charmander": ["fire"], "squirtle": ["water"],
            "pikachu": ["electric"], "mewtwo": ["psychic"], "mew": ["psychic"],
        }
        party = []
        for i, name in enumerate(names, start=1):
            p = make_pokemon(name=name, types=types_map[name])
            p.party_slot = i
            party.append(p)

        trainer = make_trainer(party=party)
        embed = party_embed(trainer)
        for name in names:
            assert name.capitalize() in embed.description

    def test_party_colour_is_fixed(self):
        trainer = make_trainer(party=[])
        embed = party_embed(trainer)
        assert embed.colour.value == 0x5865F2

    def test_returns_discord_embed(self):
        trainer = make_trainer()
        embed = party_embed(trainer)
        assert isinstance(embed, discord.Embed)


# ── bag_embed ─────────────────────────────────────────────────────────────────

class TestBagEmbed:
    def test_title_contains_username(self):
        trainer = make_trainer()
        embed = bag_embed(trainer)
        assert "Ash" in embed.title

    def test_pokeballs_field_present(self):
        trainer = make_trainer()
        embed = bag_embed(trainer)
        field_names = [f.name for f in embed.fields]
        assert "Poké Balls" in field_names

    def test_medicine_field_present(self):
        trainer = make_trainer()
        embed = bag_embed(trainer)
        field_names = [f.name for f in embed.fields]
        assert "Medicine" in field_names

    def test_pokeball_counts_shown(self):
        trainer = make_trainer()
        trainer.pokeballs = 7
        trainer.great_balls = 3
        trainer.ultra_balls = 1
        embed = bag_embed(trainer)
        balls_field = next(f for f in embed.fields if f.name == "Poké Balls")
        assert "7" in balls_field.value
        assert "3" in balls_field.value
        assert "1" in balls_field.value

    def test_medicine_counts_shown(self):
        trainer = make_trainer()
        trainer.potions = 5
        trainer.super_potions = 2
        embed = bag_embed(trainer)
        med_field = next(f for f in embed.fields if f.name == "Medicine")
        assert "5" in med_field.value
        assert "2" in med_field.value

    def test_zero_items_shown(self):
        trainer = make_trainer()
        trainer.pokeballs = 0
        trainer.potions = 0
        embed = bag_embed(trainer)
        balls_field = next(f for f in embed.fields if f.name == "Poké Balls")
        assert "0" in balls_field.value

    def test_bag_colour(self):
        trainer = make_trainer()
        embed = bag_embed(trainer)
        assert embed.colour.value == 0x9B59B6

    def test_returns_discord_embed(self):
        trainer = make_trainer()
        embed = bag_embed(trainer)
        assert isinstance(embed, discord.Embed)

    def test_two_fields_exactly(self):
        trainer = make_trainer()
        embed = bag_embed(trainer)
        assert len(embed.fields) == 2
