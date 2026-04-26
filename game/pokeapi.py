import asyncio
import json
import os
import random

import aiohttp

from .models import Move, Pokemon

POKEAPI_BASE = "https://pokeapi.co/api/v2"
MAX_POKEMON_ID = 898  # Gen 1–8
CACHE_FILE = ".pokeapi_cache.json"

_cache: dict = {}


def _load_cache() -> None:
    global _cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            _cache = json.load(f)


def _save_cache() -> None:
    with open(CACHE_FILE, "w") as f:
        json.dump(_cache, f)


_load_cache()


async def _fetch(url: str, session: aiohttp.ClientSession) -> dict:
    if url in _cache:
        return _cache[url]
    async with session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.json()
    _cache[url] = data
    _save_cache()
    return data


def _calc_stat(base: int, level: int, *, is_hp: bool = False) -> int:
    if is_hp:
        return int((2 * base * level / 100) + level + 10)
    return int((2 * base * level / 100) + 5)


async def _get_moves(
    pokemon_data: dict, level: int, session: aiohttp.ClientSession
) -> list[Move]:
    # Prefer moves learnable by level-up at or below current level
    level_up_urls = [
        entry["move"]["url"]
        for entry in pokemon_data["moves"]
        for vg in entry["version_group_details"]
        if vg["move_learn_method"]["name"] == "level-up"
        and vg["level_learned_at"] <= max(level, 1)
    ]

    if not level_up_urls:
        level_up_urls = [e["move"]["url"] for e in pokemon_data["moves"]]

    random.shuffle(level_up_urls)

    # Fetch up to 16 candidate moves concurrently, pick best 4
    tasks = [_fetch(url, session) for url in level_up_urls[:16]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    moves: list[Move] = []
    for data in results:
        if isinstance(data, Exception):
            continue
        power = data.get("power") or 0
        if power > 0 or len(moves) < 2:
            pp = data.get("pp") or 10
            moves.append(Move(
                name=data["name"].replace("-", " ").title(),
                type=data["type"]["name"],
                power=power,
                accuracy=data.get("accuracy") or 100,
                pp=pp,
                current_pp=pp,
                damage_class=data["damage_class"]["name"],
            ))
        if len(moves) >= 4:
            break

    if not moves:
        moves.append(Move("Tackle", "normal", 40, 100, 35, 35, "physical"))

    return moves[:4]


async def get_pokemon(
    pokemon_id: int,
    level: int,
    session: aiohttp.ClientSession,
    *,
    force_shiny: bool = False,
) -> Pokemon:
    poke_url = f"{POKEAPI_BASE}/pokemon/{pokemon_id}"
    spec_url = f"{POKEAPI_BASE}/pokemon-species/{pokemon_id}"

    poke_data, spec_data = await asyncio.gather(
        _fetch(poke_url, session),
        _fetch(spec_url, session),
    )

    base_stats = {s["stat"]["name"]: s["base_stat"] for s in poke_data["stats"]}
    types = [t["type"]["name"] for t in poke_data["types"]]
    catch_rate: int = spec_data.get("capture_rate", 45)

    is_shiny = force_shiny or (random.randint(1, 4096) == 1)
    sprites = poke_data["sprites"]
    if is_shiny and sprites.get("front_shiny"):
        sprite_url = sprites["front_shiny"]
    else:
        sprite_url = sprites.get("front_default") or ""
        is_shiny = False

    moves = await _get_moves(poke_data, level, session)

    return Pokemon(
        id=pokemon_id,
        name=poke_data["name"],
        types=types,
        level=level,
        xp=0,
        max_hp=_calc_stat(base_stats["hp"], level, is_hp=True),
        current_hp=_calc_stat(base_stats["hp"], level, is_hp=True),
        attack=_calc_stat(base_stats["attack"], level),
        defense=_calc_stat(base_stats["defense"], level),
        sp_attack=_calc_stat(base_stats["special-attack"], level),
        sp_defense=_calc_stat(base_stats["special-defense"], level),
        speed=_calc_stat(base_stats["speed"], level),
        moves=moves,
        sprite_url=sprite_url,
        catch_rate=catch_rate,
        is_shiny=is_shiny,
    )


async def get_random_wild(level: int, session: aiohttp.ClientSession) -> Pokemon:
    return await get_pokemon(random.randint(1, MAX_POKEMON_ID), level, session)


STARTER_IDS = {"bulbasaur": 1, "charmander": 4, "squirtle": 7}


async def get_starter(name: str, session: aiohttp.ClientSession) -> Pokemon:
    return await get_pokemon(STARTER_IDS[name.lower()], 5, session)
