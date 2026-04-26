import json
import os

import aiosqlite

from .models import Move, Pokemon, Trainer

DB_PATH = os.getenv("DB_PATH", "pokemon.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS trainers (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT    NOT NULL,
    pokeballs   INTEGER DEFAULT 5,
    great_balls INTEGER DEFAULT 0,
    ultra_balls INTEGER DEFAULT 0,
    potions     INTEGER DEFAULT 3,
    super_potions INTEGER DEFAULT 0,
    heal_cooldown REAL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS owned_pokemon (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL REFERENCES trainers(user_id),
    pokemon_id  INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    types       TEXT    NOT NULL,
    nickname    TEXT,
    level       INTEGER DEFAULT 5,
    xp          INTEGER DEFAULT 0,
    current_hp  INTEGER NOT NULL,
    max_hp      INTEGER NOT NULL,
    is_shiny    INTEGER DEFAULT 0,
    party_slot  INTEGER,
    moves       TEXT    NOT NULL,
    stats       TEXT    NOT NULL,
    sprite_url  TEXT    NOT NULL,
    catch_rate  INTEGER DEFAULT 45
);

CREATE TABLE IF NOT EXISTS active_encounters (
    user_id      INTEGER PRIMARY KEY,
    pokemon_data TEXT    NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


# ── Trainer ──────────────────────────────────────────────────────────────────

async def get_trainer(user_id: int) -> Trainer | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id,username,pokeballs,great_balls,ultra_balls,potions,super_potions FROM trainers WHERE user_id=?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None

        trainer = Trainer(
            user_id=row[0], username=row[1],
            pokeballs=row[2], great_balls=row[3], ultra_balls=row[4],
            potions=row[5], super_potions=row[6],
        )

        async with db.execute(
            "SELECT * FROM owned_pokemon WHERE owner_id=? AND party_slot IS NOT NULL ORDER BY party_slot",
            (user_id,),
        ) as cur:
            trainer.party = [_row_to_pokemon(r) for r in await cur.fetchall()]

    return trainer


async def create_trainer(user_id: int, username: str) -> Trainer:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO trainers (user_id, username) VALUES (?,?)",
            (user_id, username),
        )
        await db.commit()
    return Trainer(user_id=user_id, username=username)


async def update_trainer_items(trainer: Trainer) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE trainers SET pokeballs=?,great_balls=?,ultra_balls=?,potions=?,super_potions=? WHERE user_id=?",
            (trainer.pokeballs, trainer.great_balls, trainer.ultra_balls,
             trainer.potions, trainer.super_potions, trainer.user_id),
        )
        await db.commit()


async def get_heal_cooldown(user_id: int) -> float:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT heal_cooldown FROM trainers WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return row[0] if row else 0.0


async def set_heal_cooldown(user_id: int, timestamp: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE trainers SET heal_cooldown=? WHERE user_id=?", (timestamp, user_id)
        )
        await db.commit()


# ── Pokémon ───────────────────────────────────────────────────────────────────

async def save_pokemon_to_party(owner_id: int, pokemon: Pokemon, slot: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO owned_pokemon
               (owner_id,pokemon_id,name,types,nickname,level,xp,current_hp,max_hp,
                is_shiny,party_slot,moves,stats,sprite_url,catch_rate)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                owner_id, pokemon.id, pokemon.name,
                json.dumps(pokemon.types), pokemon.nickname,
                pokemon.level, pokemon.xp, pokemon.current_hp, pokemon.max_hp,
                int(pokemon.is_shiny), slot,
                json.dumps([_move_to_dict(m) for m in pokemon.moves]),
                json.dumps({
                    "atk": pokemon.attack, "def": pokemon.defense,
                    "spatk": pokemon.sp_attack, "spdef": pokemon.sp_defense,
                    "spd": pokemon.speed,
                }),
                pokemon.sprite_url, pokemon.catch_rate,
            ),
        )
        await db.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def update_pokemon(pokemon: Pokemon) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE owned_pokemon
               SET current_hp=?,level=?,xp=?,party_slot=?,moves=?,nickname=?
               WHERE id=?""",
            (
                pokemon.current_hp, pokemon.level, pokemon.xp,
                pokemon.party_slot,
                json.dumps([_move_to_dict(m) for m in pokemon.moves]),
                pokemon.nickname, pokemon.db_id,
            ),
        )
        await db.commit()


async def get_all_pokemon(owner_id: int) -> list[Pokemon]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM owned_pokemon WHERE owner_id=? ORDER BY id", (owner_id,)
        ) as cur:
            return [_row_to_pokemon(r) for r in await cur.fetchall()]


# ── Encounters ────────────────────────────────────────────────────────────────

async def save_encounter(user_id: int, pokemon: Pokemon) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO active_encounters (user_id,pokemon_data) VALUES (?,?)",
            (user_id, json.dumps(_pokemon_to_dict(pokemon))),
        )
        await db.commit()


async def get_encounter(user_id: int) -> Pokemon | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT pokemon_data FROM active_encounters WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
    return _dict_to_pokemon(json.loads(row[0])) if row else None


async def update_encounter(user_id: int, pokemon: Pokemon) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE active_encounters SET pokemon_data=? WHERE user_id=?",
            (json.dumps(_pokemon_to_dict(pokemon)), user_id),
        )
        await db.commit()


async def clear_encounter(user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM active_encounters WHERE user_id=?", (user_id,))
        await db.commit()


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _move_to_dict(m: Move) -> dict:
    return {
        "name": m.name, "type": m.type, "power": m.power,
        "accuracy": m.accuracy, "pp": m.pp, "current_pp": m.current_pp,
        "damage_class": m.damage_class,
    }


def _dict_to_move(d: dict) -> Move:
    return Move(**d)


def _pokemon_to_dict(p: Pokemon) -> dict:
    return {
        "id": p.id, "name": p.name, "types": p.types, "level": p.level,
        "xp": p.xp, "max_hp": p.max_hp, "current_hp": p.current_hp,
        "attack": p.attack, "defense": p.defense, "sp_attack": p.sp_attack,
        "sp_defense": p.sp_defense, "speed": p.speed,
        "moves": [_move_to_dict(m) for m in p.moves],
        "sprite_url": p.sprite_url, "is_shiny": p.is_shiny,
        "nickname": p.nickname, "db_id": p.db_id, "party_slot": p.party_slot,
        "catch_rate": p.catch_rate,
    }


def _dict_to_pokemon(d: dict) -> Pokemon:
    return Pokemon(
        id=d["id"], name=d["name"], types=d["types"],
        level=d["level"], xp=d["xp"],
        max_hp=d["max_hp"], current_hp=d["current_hp"],
        attack=d["attack"], defense=d["defense"],
        sp_attack=d["sp_attack"], sp_defense=d["sp_defense"],
        speed=d["speed"],
        moves=[_dict_to_move(m) for m in d["moves"]],
        sprite_url=d["sprite_url"], is_shiny=d.get("is_shiny", False),
        nickname=d.get("nickname"), db_id=d.get("db_id"),
        party_slot=d.get("party_slot"), catch_rate=d.get("catch_rate", 45),
    )


def _row_to_pokemon(row: tuple) -> Pokemon:
    # columns: id,owner_id,pokemon_id,name,types,nickname,level,xp,
    #          current_hp,max_hp,is_shiny,party_slot,moves,stats,sprite_url,catch_rate
    stats = json.loads(row[13])
    return Pokemon(
        id=row[2], name=row[3], types=json.loads(row[4]),
        level=row[6], xp=row[7],
        max_hp=row[9], current_hp=row[8],
        attack=stats["atk"], defense=stats["def"],
        sp_attack=stats["spatk"], sp_defense=stats["spdef"], speed=stats["spd"],
        moves=[_dict_to_move(m) for m in json.loads(row[12])],
        sprite_url=row[14], is_shiny=bool(row[10]),
        nickname=row[5], db_id=row[0], party_slot=row[11],
        catch_rate=row[15] if len(row) > 15 else 45,
    )
