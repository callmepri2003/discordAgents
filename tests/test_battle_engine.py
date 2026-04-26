
from game.battle_engine import (
    calculate_damage,
    calculate_hp_at_level,
    calculate_xp_gain,
    effectiveness_message,
    get_type_effectiveness,
    roll_crit,
)
from tests.conftest import make_move, make_pokemon


# ── Type effectiveness ────────────────────────────────────────────────────────

def test_effectiveness_super():
    assert get_type_effectiveness("water", ["fire"]) == 2.0


def test_effectiveness_resist():
    assert get_type_effectiveness("fire", ["water"]) == 0.5


def test_effectiveness_immune():
    assert get_type_effectiveness("electric", ["ground"]) == 0.0


def test_effectiveness_neutral():
    assert get_type_effectiveness("normal", ["normal"]) == 1.0


def test_effectiveness_double_weak():
    # Water vs fire/rock = 2×2 = 4×
    assert get_type_effectiveness("water", ["fire", "rock"]) == 4.0


def test_effectiveness_dual_resist():
    # Fire vs water/dragon = 0.5×0.5 = 0.25×
    assert get_type_effectiveness("fire", ["water", "dragon"]) == 0.25


def test_effectiveness_unknown_type():
    assert get_type_effectiveness("shadow", ["normal"]) == 1.0


# ── Damage calculation ────────────────────────────────────────────────────────

def test_calculate_damage_returns_positive():
    attacker = make_pokemon(attack=80, level=20)
    defender = make_pokemon(defense=50)
    move = make_move(power=80, type_="normal", damage_class="physical")
    dmg, _, _ = calculate_damage(attacker, defender, move, random_factor=1.0)
    assert dmg >= 1


def test_calculate_damage_stab_bonus():
    attacker = make_pokemon(types=["fire"], attack=80, level=20)
    defender = make_pokemon(types=["normal"], defense=50)
    move = make_move(power=80, type_="fire", damage_class="physical")
    with_stab, _, _ = calculate_damage(attacker, defender, move, random_factor=1.0)

    attacker2 = make_pokemon(types=["water"], attack=80, level=20)
    without_stab, _, _ = calculate_damage(attacker2, defender, move, random_factor=1.0)

    assert with_stab > without_stab


def test_calculate_damage_super_effective():
    attacker = make_pokemon(types=["water"], attack=80, level=20)
    defender_fire = make_pokemon(types=["fire"], defense=50)
    defender_normal = make_pokemon(types=["normal"], defense=50)
    move = make_move(power=80, type_="water", damage_class="physical")

    dmg_se, eff, _ = calculate_damage(attacker, defender_fire, move, random_factor=1.0)
    dmg_n, _, _ = calculate_damage(attacker, defender_normal, move, random_factor=1.0)

    assert eff == 2.0
    assert dmg_se > dmg_n


def test_calculate_damage_not_very_effective():
    attacker = make_pokemon(types=["fire"], attack=80, level=20)
    defender = make_pokemon(types=["water"], defense=50)
    move = make_move(power=80, type_="fire", damage_class="physical")
    _, eff, _ = calculate_damage(attacker, defender, move, random_factor=1.0)
    assert eff == 0.5


def test_calculate_damage_crit():
    attacker = make_pokemon(attack=80, level=20)
    defender = make_pokemon(defense=50)
    move = make_move(power=80, damage_class="physical")
    dmg_crit, _, is_crit = calculate_damage(attacker, defender, move, crit=True, random_factor=1.0)
    dmg_no, _, _ = calculate_damage(attacker, defender, move, crit=False, random_factor=1.0)
    assert is_crit is True
    assert dmg_crit > dmg_no


def test_calculate_damage_status_move():
    attacker = make_pokemon()
    defender = make_pokemon()
    status_move = make_move(power=0, damage_class="status")
    dmg, eff, _ = calculate_damage(attacker, defender, status_move)
    assert dmg == 0
    assert eff == 1.0


def test_calculate_damage_special_uses_spatk():
    attacker = make_pokemon(attack=10, sp_attack=200, level=20)
    defender = make_pokemon(defense=200, sp_defense=10)
    move = make_move(power=80, damage_class="special")
    special_dmg, _, _ = calculate_damage(attacker, defender, move, random_factor=1.0)

    phys_move = make_move(power=80, damage_class="physical")
    phys_dmg, _, _ = calculate_damage(attacker, defender, phys_move, random_factor=1.0)

    assert special_dmg > phys_dmg


def test_calculate_damage_immune():
    attacker = make_pokemon(types=["electric"], attack=200, level=50)
    defender = make_pokemon(types=["ground"])
    move = make_move(power=100, type_="electric", damage_class="special")
    # Damage is 0 but we still return min(1,...) — effectiveness is 0
    _, eff, _ = calculate_damage(attacker, defender, move, random_factor=1.0)
    assert eff == 0.0


# ── roll_crit ─────────────────────────────────────────────────────────────────

def test_roll_crit_returns_bool():
    result = roll_crit()
    assert isinstance(result, bool)


def test_roll_crit_roughly_correct_rate():
    hits = sum(roll_crit() for _ in range(16000))
    assert 500 < hits < 2000  # ~1000 expected at 1/16


# ── effectiveness_message ─────────────────────────────────────────────────────

def test_effectiveness_message_super():
    assert "super effective" in effectiveness_message(2.0)


def test_effectiveness_message_not_very():
    assert "not very effective" in effectiveness_message(0.5)


def test_effectiveness_message_immune():
    assert "doesn't affect" in effectiveness_message(0.0)


def test_effectiveness_message_neutral():
    assert effectiveness_message(1.0) == ""


# ── XP / level helpers ────────────────────────────────────────────────────────

def test_calculate_xp_gain_positive():
    defeated = make_pokemon(level=20)
    xp = calculate_xp_gain(defeated, winner_level=15)
    assert xp >= 1


def test_calculate_xp_gain_higher_level_more_xp():
    defeated_high = make_pokemon(level=30)
    defeated_low = make_pokemon(level=5)
    winner_level = 20
    assert calculate_xp_gain(defeated_high, winner_level) > calculate_xp_gain(
        defeated_low, winner_level
    )


def test_calculate_hp_at_level():
    hp = calculate_hp_at_level(45, 10)
    assert hp > 0
    hp_high = calculate_hp_at_level(45, 50)
    assert hp_high > hp
