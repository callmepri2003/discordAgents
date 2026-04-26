from game.models import TYPE_COLORS, TYPE_EMOJI
from tests.conftest import make_pokemon, make_trainer


# ── Pokemon.display_name ──────────────────────────────────────────────────────

def test_display_name_no_nickname():
    p = make_pokemon(name="pikachu")
    assert p.display_name == "Pikachu"


def test_display_name_with_nickname():
    p = make_pokemon(name="pikachu", nickname="Sparky")
    assert p.display_name == "Sparky"


# ── Pokemon.type_display ──────────────────────────────────────────────────────

def test_type_display_single():
    p = make_pokemon(types=["fire"])
    assert "Fire" in p.type_display
    assert TYPE_EMOJI["fire"] in p.type_display


def test_type_display_dual():
    p = make_pokemon(types=["grass", "poison"])
    assert "Grass" in p.type_display
    assert "Poison" in p.type_display


# ── Pokemon.hp_percentage ─────────────────────────────────────────────────────

def test_hp_percentage_full():
    p = make_pokemon(hp=100, current_hp=100)
    assert p.hp_percentage == 1.0


def test_hp_percentage_half():
    p = make_pokemon(hp=100, current_hp=50)
    assert p.hp_percentage == 0.5


def test_hp_percentage_zero():
    p = make_pokemon(hp=100, current_hp=0)
    assert p.hp_percentage == 0.0


def test_hp_percentage_zero_max():
    p = make_pokemon(hp=0, current_hp=0)
    assert p.hp_percentage == 0.0


# ── Pokemon.hp_bar ────────────────────────────────────────────────────────────

def test_hp_bar_full_is_green():
    p = make_pokemon(hp=100, current_hp=100)
    bar = p.hp_bar()
    assert "🟩" in bar
    assert "⬛" not in bar


def test_hp_bar_empty_has_no_blocks():
    p = make_pokemon(hp=100, current_hp=0)
    bar = p.hp_bar()
    assert "⬛" in bar
    assert "🟩" not in bar
    assert "🟨" not in bar
    assert "🟥" not in bar


def test_hp_bar_half_is_yellow():
    p = make_pokemon(hp=100, current_hp=40)  # 40% → yellow
    bar = p.hp_bar()
    assert "🟨" in bar


def test_hp_bar_critical_is_red():
    p = make_pokemon(hp=100, current_hp=10)  # 10% → red
    bar = p.hp_bar()
    assert "🟥" in bar


def test_hp_bar_custom_length():
    p = make_pokemon(hp=100, current_hp=100)
    bar = p.hp_bar(length=6)
    total_blocks = bar.count("🟩") + bar.count("🟨") + bar.count("🟥") + bar.count("⬛")
    assert total_blocks == 6


# ── Pokemon.is_fainted ────────────────────────────────────────────────────────

def test_is_fainted_true():
    p = make_pokemon(current_hp=0)
    assert p.is_fainted() is True


def test_is_fainted_false():
    p = make_pokemon(current_hp=1)
    assert p.is_fainted() is False


# ── Trainer.active_pokemon ────────────────────────────────────────────────────

def test_active_pokemon_first_healthy():
    p1 = make_pokemon(current_hp=0)
    p2 = make_pokemon(current_hp=50)
    trainer = make_trainer(party=[p1, p2])
    assert trainer.active_pokemon is p2


def test_active_pokemon_none_when_all_fainted():
    p1 = make_pokemon(current_hp=0)
    p2 = make_pokemon(current_hp=0)
    trainer = make_trainer(party=[p1, p2])
    assert trainer.active_pokemon is None


def test_active_pokemon_empty_party():
    trainer = make_trainer(party=[])
    assert trainer.active_pokemon is None


# ── Trainer.has_pokeballs ─────────────────────────────────────────────────────

def test_has_pokeballs_true():
    trainer = make_trainer()
    trainer.pokeballs = 3
    assert trainer.has_pokeballs is True


def test_has_pokeballs_great_ball_only():
    trainer = make_trainer()
    trainer.pokeballs = 0
    trainer.great_balls = 1
    assert trainer.has_pokeballs is True


def test_has_pokeballs_false():
    trainer = make_trainer()
    trainer.pokeballs = 0
    trainer.great_balls = 0
    trainer.ultra_balls = 0
    assert trainer.has_pokeballs is False


# ── Constants sanity ──────────────────────────────────────────────────────────

def test_type_emoji_coverage():
    for t in ["fire", "water", "grass", "electric", "normal"]:
        assert t in TYPE_EMOJI


def test_type_colors_coverage():
    for t in ["fire", "water", "grass", "electric"]:
        assert t in TYPE_COLORS
        assert isinstance(TYPE_COLORS[t], int)


# ── Edge-case: shiny flag in display ─────────────────────────────────────────

def test_display_name_shiny_flag_does_not_affect_display_name():
    """is_shiny doesn't change display_name — it's only used by embed builders."""
    p = make_pokemon(name="pikachu", is_shiny=True)
    assert p.display_name == "Pikachu"


def test_shiny_pokemon_is_shiny_true():
    p = make_pokemon(is_shiny=True)
    assert p.is_shiny is True


def test_non_shiny_pokemon_is_shiny_false():
    p = make_pokemon(is_shiny=False)
    assert p.is_shiny is False


# ── Edge-case: hp_bar at exactly 50% and 25% boundaries ─────────────────────

def test_hp_bar_exactly_50_percent_is_yellow():
    """At exactly 50% HP (not >50%), colour is yellow."""
    p = make_pokemon(hp=100, current_hp=50)
    bar = p.hp_bar()
    # 50% is NOT > 0.5, so it falls into the "yellow" bucket (> 0.25)
    assert "🟨" in bar


def test_hp_bar_just_above_50_percent_is_green():
    """Just above 50% HP should be green."""
    p = make_pokemon(hp=100, current_hp=51)
    bar = p.hp_bar()
    assert "🟩" in bar


def test_hp_bar_exactly_25_percent_is_red():
    """At exactly 25% HP (not >25%), colour is red."""
    p = make_pokemon(hp=100, current_hp=25)
    bar = p.hp_bar()
    # 25% is NOT > 0.25, so it falls into the red bucket
    assert "🟥" in bar


def test_hp_bar_just_above_25_percent_is_yellow():
    """Just above 25% HP should be yellow."""
    p = make_pokemon(hp=100, current_hp=26)
    bar = p.hp_bar()
    assert "🟨" in bar


# ── Edge-case: party with 6 Pokémon ─────────────────────────────────────────

def test_active_pokemon_returns_first_healthy_in_full_party():
    """With 6 pokemon, active_pokemon should return the first non-fainted."""
    fainted = [make_pokemon(current_hp=0) for _ in range(3)]
    alive = [make_pokemon(current_hp=50) for _ in range(3)]
    trainer = make_trainer(party=fainted + alive)
    assert trainer.active_pokemon is alive[0]


def test_party_with_six_pokemon():
    """Trainer can hold a party of 6 Pokémon."""
    party = [make_pokemon(name=f"poke{i}") for i in range(6)]
    trainer = make_trainer(party=party)
    assert len(trainer.party) == 6


def test_all_fainted_in_full_party():
    """If all 6 Pokémon faint, active_pokemon is None."""
    party = [make_pokemon(current_hp=0) for _ in range(6)]
    trainer = make_trainer(party=party)
    assert trainer.active_pokemon is None
