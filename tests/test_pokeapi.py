"""
Tests for game/pokeapi.py.
Mocks aiohttp using aioresponses so no real HTTP calls are made.
"""
import json
import os
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

import game.pokeapi as pokeapi_module
from game.pokeapi import (
    POKEAPI_BASE,
    _calc_stat,
    _get_moves,
    _load_cache,
    _save_cache,
    get_pokemon,
)
from game.models import Move, Pokemon


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_cache(monkeypatch, tmp_path):
    """Ensure in-memory cache is empty and CACHE_FILE points to tmp dir."""
    monkeypatch.setattr(pokeapi_module, "_cache", {})
    cache_file = str(tmp_path / ".pokeapi_cache.json")
    monkeypatch.setattr(pokeapi_module, "CACHE_FILE", cache_file)
    return cache_file


# ── Minimal fake API payloads ─────────────────────────────────────────────────

def _make_poke_payload(pokemon_id=25, name="pikachu", types=None, shiny_url="shiny.png"):
    if types is None:
        types = [{"type": {"name": "electric"}}]
    return {
        "id": pokemon_id,
        "name": name,
        "types": types,
        "stats": [
            {"stat": {"name": "hp"}, "base_stat": 35},
            {"stat": {"name": "attack"}, "base_stat": 55},
            {"stat": {"name": "defense"}, "base_stat": 40},
            {"stat": {"name": "special-attack"}, "base_stat": 50},
            {"stat": {"name": "special-defense"}, "base_stat": 50},
            {"stat": {"name": "speed"}, "base_stat": 90},
        ],
        "sprites": {
            "front_default": "default.png",
            "front_shiny": shiny_url,
        },
        "moves": [
            {
                "move": {"name": "thunder-shock", "url": f"{POKEAPI_BASE}/move/84"},
                "version_group_details": [
                    {
                        "move_learn_method": {"name": "level-up"},
                        "level_learned_at": 1,
                    }
                ],
            }
        ],
    }


def _make_species_payload(capture_rate=190):
    return {"capture_rate": capture_rate}


def _make_move_payload(name="thunder-shock", power=40, pp=30, accuracy=100, move_type="electric", damage_class="special"):
    return {
        "name": name,
        "power": power,
        "pp": pp,
        "accuracy": accuracy,
        "type": {"name": move_type},
        "damage_class": {"name": damage_class},
    }


# ── _calc_stat ────────────────────────────────────────────────────────────────

class TestCalcStat:
    def test_hp_stat_level_5(self):
        result = _calc_stat(45, 5, is_hp=True)
        # (2*45*5/100) + 5 + 10 = 4.5 + 15 = 19 (int truncated)
        expected = int((2 * 45 * 5 / 100) + 5 + 10)
        assert result == expected

    def test_non_hp_stat_level_5(self):
        result = _calc_stat(55, 5, is_hp=False)
        expected = int((2 * 55 * 5 / 100) + 5)
        assert result == expected

    def test_hp_higher_than_non_hp_same_base(self):
        hp = _calc_stat(50, 10, is_hp=True)
        non_hp = _calc_stat(50, 10, is_hp=False)
        assert hp > non_hp

    def test_higher_level_higher_stat(self):
        low = _calc_stat(50, 10, is_hp=False)
        high = _calc_stat(50, 50, is_hp=False)
        assert high > low

    def test_higher_base_higher_stat(self):
        low_base = _calc_stat(30, 20, is_hp=False)
        high_base = _calc_stat(100, 20, is_hp=False)
        assert high_base > low_base

    def test_returns_int(self):
        assert isinstance(_calc_stat(45, 10, is_hp=True), int)
        assert isinstance(_calc_stat(45, 10, is_hp=False), int)

    def test_level_100_hp(self):
        result = _calc_stat(45, 100, is_hp=True)
        expected = int((2 * 45 * 100 / 100) + 100 + 10)
        assert result == expected

    def test_level_1_hp(self):
        result = _calc_stat(45, 1, is_hp=True)
        expected = int((2 * 45 * 1 / 100) + 1 + 10)
        assert result == expected


# ── cache load / save ─────────────────────────────────────────────────────────

class TestCache:
    def test_save_and_load_cache(self, tmp_path, monkeypatch):
        data = {"https://example.com": {"key": "value"}}
        monkeypatch.setattr(pokeapi_module, "_cache", dict(data))
        _save_cache()
        monkeypatch.setattr(pokeapi_module, "_cache", {})
        _load_cache()
        assert pokeapi_module._cache == data

    def test_load_cache_missing_file(self, monkeypatch, tmp_path):
        """Loading from a nonexistent file leaves cache empty."""
        monkeypatch.setattr(pokeapi_module, "CACHE_FILE", str(tmp_path / "no_such_file.json"))
        monkeypatch.setattr(pokeapi_module, "_cache", {})
        _load_cache()
        assert pokeapi_module._cache == {}

    def test_save_cache_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pokeapi_module, "_cache", {"url": {"data": 1}})
        _save_cache()
        assert os.path.exists(pokeapi_module.CACHE_FILE)
        with open(pokeapi_module.CACHE_FILE) as f:
            saved = json.load(f)
        assert saved == {"url": {"data": 1}}


# ── _get_moves ────────────────────────────────────────────────────────────────

class TestGetMoves:
    async def test_returns_moves_list(self):
        import aiohttp

        move_url = f"{POKEAPI_BASE}/move/84"
        move_payload = _make_move_payload()
        pokemon_data = {
            "moves": [
                {
                    "move": {"name": "thunder-shock", "url": move_url},
                    "version_group_details": [
                        {"move_learn_method": {"name": "level-up"}, "level_learned_at": 1}
                    ],
                }
            ]
        }

        with aioresponses() as mocked:
            mocked.get(move_url, payload=move_payload)
            async with aiohttp.ClientSession() as session:
                moves = await _get_moves(pokemon_data, level=10, session=session)

        assert len(moves) >= 1
        assert all(isinstance(m, Move) for m in moves)

    async def test_falls_back_to_tackle_when_no_moves(self):
        """When all moves have power=0 and we get <2 total, Tackle is used as fallback."""
        import aiohttp

        # pokemon_data with no moves at all
        pokemon_data = {"moves": []}

        with aioresponses():
            async with aiohttp.ClientSession() as session:
                moves = await _get_moves(pokemon_data, level=5, session=session)

        assert len(moves) >= 1
        assert moves[0].name == "Tackle"

    async def test_capped_at_four_moves(self):
        """At most 4 moves are returned."""
        import aiohttp

        move_urls = [f"{POKEAPI_BASE}/move/{i}" for i in range(1, 10)]
        pokemon_data = {
            "moves": [
                {
                    "move": {"name": f"move-{i}", "url": url},
                    "version_group_details": [
                        {"move_learn_method": {"name": "level-up"}, "level_learned_at": 1}
                    ],
                }
                for i, url in enumerate(move_urls, start=1)
            ]
        }

        with aioresponses() as mocked:
            for i, url in enumerate(move_urls, start=1):
                mocked.get(url, payload=_make_move_payload(
                    name=f"move-{i}", power=40 + i,
                ))
            async with aiohttp.ClientSession() as session:
                moves = await _get_moves(pokemon_data, level=10, session=session)

        assert len(moves) <= 4

    async def test_move_format_correctness(self):
        """Move name is title-cased and dashes replaced with spaces."""
        import aiohttp

        move_url = f"{POKEAPI_BASE}/move/84"
        move_payload = _make_move_payload(name="thunder-shock")
        pokemon_data = {
            "moves": [
                {
                    "move": {"name": "thunder-shock", "url": move_url},
                    "version_group_details": [
                        {"move_learn_method": {"name": "level-up"}, "level_learned_at": 1}
                    ],
                }
            ]
        }

        with aioresponses() as mocked:
            mocked.get(move_url, payload=move_payload)
            async with aiohttp.ClientSession() as session:
                moves = await _get_moves(pokemon_data, level=10, session=session)

        assert moves[0].name == "Thunder Shock"


# ── get_pokemon end-to-end ────────────────────────────────────────────────────

class TestGetPokemon:
    async def test_get_pokemon_returns_pokemon(self):
        import aiohttp

        poke_url = f"{POKEAPI_BASE}/pokemon/25"
        spec_url = f"{POKEAPI_BASE}/pokemon-species/25"
        move_url = f"{POKEAPI_BASE}/move/84"

        poke_payload = _make_poke_payload()
        spec_payload = _make_species_payload(capture_rate=190)
        move_payload = _make_move_payload()

        with aioresponses() as mocked:
            mocked.get(poke_url, payload=poke_payload)
            mocked.get(spec_url, payload=spec_payload)
            mocked.get(move_url, payload=move_payload)

            async with aiohttp.ClientSession() as session:
                with patch("random.randint", return_value=999):  # not shiny
                    p = await get_pokemon(25, level=10, session=session)

        assert isinstance(p, Pokemon)
        assert p.id == 25
        assert p.name == "pikachu"
        assert p.level == 10
        assert p.catch_rate == 190
        assert "electric" in p.types

    async def test_get_pokemon_stats_calculated(self):
        import aiohttp

        poke_url = f"{POKEAPI_BASE}/pokemon/25"
        spec_url = f"{POKEAPI_BASE}/pokemon-species/25"
        move_url = f"{POKEAPI_BASE}/move/84"

        poke_payload = _make_poke_payload()
        spec_payload = _make_species_payload()
        move_payload = _make_move_payload()

        with aioresponses() as mocked:
            mocked.get(poke_url, payload=poke_payload)
            mocked.get(spec_url, payload=spec_payload)
            mocked.get(move_url, payload=move_payload)

            async with aiohttp.ClientSession() as session:
                with patch("random.randint", return_value=999):
                    p = await get_pokemon(25, level=10, session=session)

        # Verify HP is computed correctly
        expected_hp = _calc_stat(35, 10, is_hp=True)
        assert p.max_hp == expected_hp
        assert p.current_hp == expected_hp

    async def test_get_pokemon_shiny_forced(self):
        import aiohttp

        poke_url = f"{POKEAPI_BASE}/pokemon/25"
        spec_url = f"{POKEAPI_BASE}/pokemon-species/25"
        move_url = f"{POKEAPI_BASE}/move/84"

        poke_payload = _make_poke_payload(shiny_url="shiny_sprite.png")
        spec_payload = _make_species_payload()
        move_payload = _make_move_payload()

        with aioresponses() as mocked:
            mocked.get(poke_url, payload=poke_payload)
            mocked.get(spec_url, payload=spec_payload)
            mocked.get(move_url, payload=move_payload)

            async with aiohttp.ClientSession() as session:
                p = await get_pokemon(25, level=10, session=session, force_shiny=True)

        assert p.is_shiny is True
        assert p.sprite_url == "shiny_sprite.png"

    async def test_get_pokemon_not_shiny_uses_default_sprite(self):
        import aiohttp

        poke_url = f"{POKEAPI_BASE}/pokemon/25"
        spec_url = f"{POKEAPI_BASE}/pokemon-species/25"
        move_url = f"{POKEAPI_BASE}/move/84"

        poke_payload = _make_poke_payload()
        spec_payload = _make_species_payload()
        move_payload = _make_move_payload()

        with aioresponses() as mocked:
            mocked.get(poke_url, payload=poke_payload)
            mocked.get(spec_url, payload=spec_payload)
            mocked.get(move_url, payload=move_payload)

            async with aiohttp.ClientSession() as session:
                with patch("random.randint", return_value=999):  # not shiny
                    p = await get_pokemon(25, level=10, session=session)

        assert p.is_shiny is False
        assert p.sprite_url == "default.png"

    async def test_get_pokemon_uses_cache_on_second_call(self, monkeypatch):
        """Second call for same URL should use in-memory cache, no extra HTTP calls."""
        import aiohttp

        poke_url = f"{POKEAPI_BASE}/pokemon/25"
        spec_url = f"{POKEAPI_BASE}/pokemon-species/25"
        move_url = f"{POKEAPI_BASE}/move/84"

        poke_payload = _make_poke_payload()
        spec_payload = _make_species_payload()
        move_payload = _make_move_payload()

        with aioresponses() as mocked:
            # Only register each URL once — if cache works, second call won't hit HTTP
            mocked.get(poke_url, payload=poke_payload)
            mocked.get(spec_url, payload=spec_payload)
            mocked.get(move_url, payload=move_payload)

            async with aiohttp.ClientSession() as session:
                with patch("random.randint", return_value=999):
                    p1 = await get_pokemon(25, level=10, session=session)
                with patch("random.randint", return_value=999):
                    # Second call — URLs already cached, no ConnectionError
                    p2 = await get_pokemon(25, level=10, session=session)

        assert p1.name == p2.name

    async def test_get_pokemon_dual_type(self):
        import aiohttp

        poke_url = f"{POKEAPI_BASE}/pokemon/1"
        spec_url = f"{POKEAPI_BASE}/pokemon-species/1"
        move_url = f"{POKEAPI_BASE}/move/84"

        poke_payload = _make_poke_payload(
            pokemon_id=1, name="bulbasaur",
            types=[{"type": {"name": "grass"}}, {"type": {"name": "poison"}}],
        )
        spec_payload = _make_species_payload(capture_rate=45)
        move_payload = _make_move_payload()

        with aioresponses() as mocked:
            mocked.get(poke_url, payload=poke_payload)
            mocked.get(spec_url, payload=spec_payload)
            mocked.get(move_url, payload=move_payload)

            async with aiohttp.ClientSession() as session:
                with patch("random.randint", return_value=999):
                    p = await get_pokemon(1, level=5, session=session)

        assert p.types == ["grass", "poison"]
        assert p.catch_rate == 45

    async def test_get_pokemon_no_shiny_sprite_falls_back(self):
        """If front_shiny is missing/None but force_shiny=True, falls back to non-shiny."""
        import aiohttp

        poke_url = f"{POKEAPI_BASE}/pokemon/25"
        spec_url = f"{POKEAPI_BASE}/pokemon-species/25"
        move_url = f"{POKEAPI_BASE}/move/84"

        # No shiny sprite
        poke_payload = _make_poke_payload(shiny_url=None)
        poke_payload["sprites"]["front_shiny"] = None
        spec_payload = _make_species_payload()
        move_payload = _make_move_payload()

        with aioresponses() as mocked:
            mocked.get(poke_url, payload=poke_payload)
            mocked.get(spec_url, payload=spec_payload)
            mocked.get(move_url, payload=move_payload)

            async with aiohttp.ClientSession() as session:
                p = await get_pokemon(25, level=10, session=session, force_shiny=True)

        # Without a shiny sprite URL, is_shiny should be False
        assert p.is_shiny is False
        assert p.sprite_url == "default.png"
