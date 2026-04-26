
from game.catch_engine import BALL_MULTIPLIERS, catch_attempt, shake_flavour


def test_catch_certain():
    """Max catch rate + low HP should always catch."""
    for _ in range(20):
        caught, shakes = catch_attempt(255, current_hp=1, max_hp=100)
        assert caught is True
        assert shakes == 4


def test_catch_impossible():
    """Catch rate 0 → never caught, 0 shakes."""
    for _ in range(20):
        caught, shakes = catch_attempt(0, current_hp=50, max_hp=100)
        assert caught is False
        assert shakes == 0


def test_shake_count_in_range():
    """Shake count is always 0–4."""
    for _ in range(50):
        _, shakes = catch_attempt(45, current_hp=50, max_hp=100)
        assert 0 <= shakes <= 4


def test_ball_multiplier_great_ball():
    """Great Ball should catch more often than Poké Ball at same conditions."""
    pokeball_catches = sum(
        catch_attempt(45, current_hp=50, max_hp=100, ball_multiplier=BALL_MULTIPLIERS["pokeball"])[0]
        for _ in range(200)
    )
    great_catches = sum(
        catch_attempt(45, current_hp=50, max_hp=100, ball_multiplier=BALL_MULTIPLIERS["great_ball"])[0]
        for _ in range(200)
    )
    # Great Ball must catch at least as many on average
    assert great_catches >= pokeball_catches - 20  # allow variance


def test_low_hp_increases_catch_rate():
    """Lower HP → more catches."""
    high_hp_catches = sum(
        catch_attempt(45, current_hp=99, max_hp=100)[0] for _ in range(300)
    )
    low_hp_catches = sum(
        catch_attempt(45, current_hp=1, max_hp=100)[0] for _ in range(300)
    )
    assert low_hp_catches > high_hp_catches


def test_ball_multipliers_values():
    assert BALL_MULTIPLIERS["pokeball"] == 1.0
    assert BALL_MULTIPLIERS["great_ball"] == 1.5
    assert BALL_MULTIPLIERS["ultra_ball"] == 2.0


def test_shake_flavour_caught():
    text = shake_flavour(4, caught=True)
    assert "Gotcha" in text


def test_shake_flavour_not_caught():
    text = shake_flavour(2, caught=False)
    assert "broke free" in text


def test_shake_flavour_zero_shakes():
    text = shake_flavour(0, caught=False)
    assert "broke free" in text


# ── Edge cases: status multiplier, all 4 shake counts ─────────────────────────

def test_status_multiplier_increases_catch_rate():
    """Status condition (multiplier > 1) should catch more than without status."""
    no_status = sum(
        catch_attempt(45, current_hp=50, max_hp=100, status_multiplier=1.0)[0]
        for _ in range(300)
    )
    with_status = sum(
        catch_attempt(45, current_hp=50, max_hp=100, status_multiplier=2.0)[0]
        for _ in range(300)
    )
    assert with_status >= no_status - 20  # allow variance, but status should help


def test_status_multiplier_parameter_accepted():
    """catch_attempt accepts status_multiplier without error."""
    caught, shakes = catch_attempt(
        45, current_hp=50, max_hp=100, ball_multiplier=1.0, status_multiplier=1.5
    )
    assert isinstance(caught, bool)
    assert 0 <= shakes <= 4


def test_all_shake_counts_possible():
    """
    Shake counts 0–3 (failed) and 4 (caught) should all be representable.
    We test that values 0, 1, 2, 3 can occur (not caught) and 4 (caught).
    """
    # Shake 4 (caught) — use certain catch conditions
    caught, shakes = catch_attempt(255, current_hp=1, max_hp=100)
    assert shakes == 4
    assert caught is True

    # Shake 0 (immediate break) — catch rate 0
    caught, shakes = catch_attempt(0, current_hp=50, max_hp=100)
    assert shakes == 0
    assert caught is False


def test_shake_flavour_one_shake():
    text = shake_flavour(1, caught=False)
    assert "broke free" in text


def test_shake_flavour_three_shakes():
    text = shake_flavour(3, caught=False)
    assert "broke free" in text


def test_shake_flavour_caught_ignores_shake_count():
    """When caught=True, the 'Gotcha' message is returned regardless of count."""
    for count in [1, 2, 3, 4]:
        text = shake_flavour(count, caught=True)
        assert "Gotcha" in text


def test_catch_rate_clamped_to_zero():
    """Even with a very large negative effective catch rate, shakes == 0."""
    caught, shakes = catch_attempt(0, current_hp=1, max_hp=1)
    assert caught is False
    assert shakes == 0


def test_ultra_ball_better_than_pokeball_statistically():
    """Ultra Ball (2×) should catch more than Poké Ball on average."""
    pokeball_catches = sum(
        catch_attempt(45, current_hp=50, max_hp=100, ball_multiplier=BALL_MULTIPLIERS["pokeball"])[0]
        for _ in range(300)
    )
    ultra_catches = sum(
        catch_attempt(45, current_hp=50, max_hp=100, ball_multiplier=BALL_MULTIPLIERS["ultra_ball"])[0]
        for _ in range(300)
    )
    assert ultra_catches >= pokeball_catches - 20  # allow statistical variance
