import math
import random

BALL_MULTIPLIERS: dict[str, float] = {
    "pokeball": 1.0,
    "great_ball": 1.5,
    "ultra_ball": 2.0,
}


def catch_attempt(
    base_catch_rate: int,
    current_hp: int,
    max_hp: int,
    ball_multiplier: float = 1.0,
    status_multiplier: float = 1.0,
) -> tuple[bool, int]:
    """
    Gen 6+ catch formula. Returns (caught, shake_count).
    shake_count is 0–4; caught is True when shake_count == 4.
    """
    a = (
        (3 * max_hp - 2 * current_hp)
        * base_catch_rate
        * ball_multiplier
        * status_multiplier
    ) / (3 * max_hp)
    a = max(0.0, min(255.0, a))

    if a == 0.0:
        return False, 0

    b = int(65536 / math.pow(255 / a, 0.1875))

    shakes = 0
    for _ in range(4):
        if random.randint(0, 65535) < b:
            shakes += 1
        else:
            break

    return shakes == 4, shakes


def shake_flavour(shakes: int, caught: bool) -> str:
    if caught:
        return "The ball wobbled once... twice... three times... **Gotcha!** 🎉"
    lines = ["The ball wobbled..." + " again..." * i for i in range(shakes)]
    lines.append("Oh no! The Pokémon **broke free!** 💨")
    return "\n".join(lines)
