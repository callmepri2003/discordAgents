import random
from .models import Pokemon, Move

# Attacker type → defender type → multiplier
TYPE_CHART: dict[str, dict[str, float]] = {
    "normal":   {"rock": 0.5, "ghost": 0.0, "steel": 0.5},
    "fire":     {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "dragon": 0.5, "steel": 2.0},
    "water":    {"fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0, "dragon": 0.5},
    "electric": {"water": 2.0, "electric": 0.5, "grass": 0.5, "ground": 0.0, "flying": 2.0, "dragon": 0.5},
    "grass":    {"fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5, "rock": 2.0, "dragon": 0.5, "steel": 0.5},
    "ice":      {"water": 0.5, "grass": 2.0, "ice": 0.5, "ground": 2.0, "flying": 2.0, "dragon": 2.0, "steel": 0.5},
    "fighting": {"normal": 2.0, "ice": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2.0, "ghost": 0.0, "dark": 2.0, "steel": 2.0, "fairy": 0.5},
    "poison":   {"grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0.0, "fairy": 2.0},
    "ground":   {"fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0.0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
    "flying":   {"electric": 0.5, "grass": 2.0, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
    "psychic":  {"fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0.0, "steel": 0.5},
    "bug":      {"fire": 0.5, "grass": 2.0, "fighting": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
    "rock":     {"fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
    "ghost":    {"normal": 0.0, "psychic": 2.0, "ghost": 2.0, "dark": 0.5},
    "dragon":   {"dragon": 2.0, "steel": 0.5, "fairy": 0.0},
    "dark":     {"fighting": 0.5, "psychic": 2.0, "ghost": 2.0, "dark": 0.5, "fairy": 0.5},
    "steel":    {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2.0, "rock": 2.0, "steel": 0.5, "fairy": 2.0},
    "fairy":    {"fire": 0.5, "fighting": 2.0, "poison": 0.5, "dragon": 2.0, "dark": 2.0, "steel": 0.5},
}


def get_type_effectiveness(move_type: str, defender_types: list[str]) -> float:
    multiplier = 1.0
    chart = TYPE_CHART.get(move_type, {})
    for dtype in defender_types:
        multiplier *= chart.get(dtype, 1.0)
    return multiplier


def calculate_damage(
    attacker: Pokemon,
    defender: Pokemon,
    move: Move,
    *,
    crit: bool = False,
    random_factor: float | None = None,
) -> tuple[int, float, bool]:
    """Returns (damage, type_effectiveness, is_crit). Uses Gen 5 damage formula."""
    if move.power == 0 or move.damage_class == "status":
        return 0, 1.0, False

    atk = attacker.attack if move.damage_class == "physical" else attacker.sp_attack
    def_ = defender.defense if move.damage_class == "physical" else defender.sp_defense

    base = ((2 * attacker.level / 5 + 2) * move.power * atk / def_) / 50 + 2

    if move.type in attacker.types:
        base *= 1.5  # STAB

    effectiveness = get_type_effectiveness(move.type, defender.types)
    base *= effectiveness

    if crit:
        base *= 1.5

    if random_factor is None:
        random_factor = random.uniform(0.85, 1.0)
    base *= random_factor

    return max(1, int(base)), effectiveness, crit


def roll_crit() -> bool:
    return random.randint(1, 16) == 1


def effectiveness_message(multiplier: float) -> str:
    if multiplier == 0.0:
        return "It doesn't affect the opposing Pokémon..."
    if multiplier < 1.0:
        return "It's not very effective..."
    if multiplier > 1.0:
        return "It's super effective!"
    return ""


def calculate_xp_gain(defeated: Pokemon, winner_level: int) -> int:
    base = max(10, defeated.level * 3)
    return max(1, int(base * defeated.level / (7 * winner_level)))


def calculate_hp_at_level(base_hp: int, level: int) -> int:
    return int((2 * base_hp * level / 100) + level + 10)
