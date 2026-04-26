"""
Comprehensive tests for game/database.py.
Uses a real temp SQLite file (tmp_path fixture) for every test.
DB_PATH is monkeypatched before each test to isolate state.
"""

import pytest

import game.database as db_module
from game.database import (
    _dict_to_move,
    _dict_to_pokemon,
    _move_to_dict,
    _pokemon_to_dict,
    clear_encounter,
    create_trainer,
    get_all_pokemon,
    get_encounter,
    get_heal_cooldown,
    get_trainer,
    init_db,
    save_encounter,
    save_pokemon_to_party,
    set_heal_cooldown,
    update_encounter,
    update_pokemon,
    update_trainer_items,
)
from tests.conftest import make_move, make_pokemon


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_db_path(tmp_path, monkeypatch):
    """Redirect every DB call to an isolated temp file."""
    db_file = str(tmp_path / "test_pokemon.db")
    monkeypatch.setattr(db_module, "DB_PATH", db_file)
    return db_file


# ── Serialisation helpers ─────────────────────────────────────────────────────

class TestMoveSerialisation:
    def test_move_to_dict_fields(self):
        m = make_move(name="Flamethrower", type_="fire", power=90, accuracy=100, pp=15, current_pp=15, damage_class="special")
        d = _move_to_dict(m)
        assert d["name"] == "Flamethrower"
        assert d["type"] == "fire"
        assert d["power"] == 90
        assert d["accuracy"] == 100
        assert d["pp"] == 15
        assert d["current_pp"] == 15
        assert d["damage_class"] == "special"

    def test_dict_to_move_roundtrip(self):
        m = make_move(name="Surf", type_="water", power=90, accuracy=100, pp=15, damage_class="special")
        result = _dict_to_move(_move_to_dict(m))
        assert result.name == m.name
        assert result.type == m.type
        assert result.power == m.power
        assert result.accuracy == m.accuracy
        assert result.pp == m.pp
        assert result.current_pp == m.current_pp
        assert result.damage_class == m.damage_class

    def test_move_to_dict_status_move(self):
        m = make_move(name="Growl", power=0, damage_class="status")
        d = _move_to_dict(m)
        assert d["power"] == 0
        assert d["damage_class"] == "status"

    def test_dict_to_move_preserves_current_pp(self):
        m = make_move(pp=20, current_pp=5)
        d = _move_to_dict(m)
        result = _dict_to_move(d)
        assert result.current_pp == 5


class TestPokemonSerialisation:
    def test_pokemon_to_dict_fields(self):
        p = make_pokemon(id_=25, name="pikachu", types=["electric"], level=15, is_shiny=True)
        d = _pokemon_to_dict(p)
        assert d["id"] == 25
        assert d["name"] == "pikachu"
        assert d["types"] == ["electric"]
        assert d["level"] == 15
        assert d["is_shiny"] is True
        assert "moves" in d
        assert isinstance(d["moves"], list)

    def test_dict_to_pokemon_roundtrip(self):
        p = make_pokemon(
            id_=4, name="charmander", types=["fire"], level=10,
            is_shiny=False, nickname="Flamey", catch_rate=45,
        )
        result = _dict_to_pokemon(_pokemon_to_dict(p))
        assert result.id == p.id
        assert result.name == p.name
        assert result.types == p.types
        assert result.level == p.level
        assert result.is_shiny == p.is_shiny
        assert result.nickname == p.nickname
        assert result.catch_rate == p.catch_rate

    def test_dict_to_pokemon_defaults(self):
        """Missing optional keys default gracefully."""
        d = {
            "id": 1, "name": "bulbasaur", "types": ["grass", "poison"],
            "level": 5, "xp": 0, "max_hp": 45, "current_hp": 45,
            "attack": 49, "defense": 49, "sp_attack": 65, "sp_defense": 65,
            "speed": 45, "moves": [], "sprite_url": "", "catch_rate": 45,
        }
        p = _dict_to_pokemon(d)
        assert p.is_shiny is False
        assert p.nickname is None
        assert p.db_id is None
        assert p.party_slot is None

    def test_pokemon_to_dict_moves_serialised(self):
        moves = [
            make_move(name="Tackle", power=40),
            make_move(name="Growl", power=0, damage_class="status"),
        ]
        p = make_pokemon(moves=moves)
        d = _pokemon_to_dict(p)
        assert len(d["moves"]) == 2
        assert d["moves"][0]["name"] == "Tackle"
        assert d["moves"][1]["name"] == "Growl"

    def test_shiny_flag_preserved(self):
        p = make_pokemon(is_shiny=True)
        d = _pokemon_to_dict(p)
        result = _dict_to_pokemon(d)
        assert result.is_shiny is True

    def test_non_shiny_flag_preserved(self):
        p = make_pokemon(is_shiny=False)
        d = _pokemon_to_dict(p)
        result = _dict_to_pokemon(d)
        assert result.is_shiny is False


# ── init_db ───────────────────────────────────────────────────────────────────

class TestInitDb:
    async def test_creates_tables(self, tmp_path):
        await init_db()
        import aiosqlite
        db_path = db_module.DB_PATH
        async with aiosqlite.connect(db_path) as con:
            async with con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ) as cur:
                tables = {r[0] for r in await cur.fetchall()}
        assert "trainers" in tables
        assert "owned_pokemon" in tables
        assert "active_encounters" in tables

    async def test_idempotent(self):
        """init_db can be called multiple times without error."""
        await init_db()
        await init_db()


# ── create_trainer / get_trainer ──────────────────────────────────────────────

class TestTrainerCrud:
    async def test_create_trainer_returns_trainer(self):
        await init_db()
        trainer = await create_trainer(1001, "Ash")
        assert trainer.user_id == 1001
        assert trainer.username == "Ash"
        assert trainer.pokeballs == 5
        assert trainer.potions == 3

    async def test_get_trainer_none_if_not_exists(self):
        await init_db()
        result = await get_trainer(9999)
        assert result is None

    async def test_get_trainer_returns_trainer(self):
        await init_db()
        await create_trainer(1002, "Misty")
        trainer = await get_trainer(1002)
        assert trainer is not None
        assert trainer.user_id == 1002
        assert trainer.username == "Misty"

    async def test_get_trainer_empty_party_by_default(self):
        await init_db()
        await create_trainer(1003, "Brock")
        trainer = await get_trainer(1003)
        assert trainer.party == []

    async def test_trainer_default_items(self):
        await init_db()
        await create_trainer(2001, "Gary")
        trainer = await get_trainer(2001)
        assert trainer.pokeballs == 5
        assert trainer.great_balls == 0
        assert trainer.ultra_balls == 0
        assert trainer.potions == 3
        assert trainer.super_potions == 0


# ── update_trainer_items ──────────────────────────────────────────────────────

class TestUpdateTrainerItems:
    async def test_update_items(self):
        await init_db()
        await create_trainer(3001, "Trainer3001")
        trainer = await get_trainer(3001)
        trainer.pokeballs = 10
        trainer.great_balls = 5
        trainer.ultra_balls = 2
        trainer.potions = 1
        trainer.super_potions = 3
        await update_trainer_items(trainer)

        refreshed = await get_trainer(3001)
        assert refreshed.pokeballs == 10
        assert refreshed.great_balls == 5
        assert refreshed.ultra_balls == 2
        assert refreshed.potions == 1
        assert refreshed.super_potions == 3

    async def test_update_items_zero(self):
        await init_db()
        await create_trainer(3002, "Trainer3002")
        trainer = await get_trainer(3002)
        trainer.pokeballs = 0
        trainer.potions = 0
        await update_trainer_items(trainer)

        refreshed = await get_trainer(3002)
        assert refreshed.pokeballs == 0
        assert refreshed.potions == 0


# ── heal cooldown ─────────────────────────────────────────────────────────────

class TestHealCooldown:
    async def test_get_heal_cooldown_default_zero(self):
        await init_db()
        await create_trainer(4001, "Healer")
        val = await get_heal_cooldown(4001)
        assert val == 0.0

    async def test_set_and_get_cooldown(self):
        await init_db()
        await create_trainer(4002, "Healer2")
        ts = 1700000000.0
        await set_heal_cooldown(4002, ts)
        val = await get_heal_cooldown(4002)
        assert val == pytest.approx(ts)

    async def test_get_heal_cooldown_missing_user(self):
        await init_db()
        val = await get_heal_cooldown(9999)
        assert val == 0.0

    async def test_overwrite_cooldown(self):
        await init_db()
        await create_trainer(4003, "Healer3")
        await set_heal_cooldown(4003, 1000.0)
        await set_heal_cooldown(4003, 2000.0)
        val = await get_heal_cooldown(4003)
        assert val == pytest.approx(2000.0)


# ── save_pokemon_to_party / update_pokemon / get_all_pokemon ─────────────────

class TestPokemonCrud:
    async def test_save_pokemon_to_party_returns_id(self):
        await init_db()
        await create_trainer(5001, "PokeFan")
        p = make_pokemon(id_=25, name="pikachu")
        row_id = await save_pokemon_to_party(5001, p, slot=1)
        assert isinstance(row_id, int)
        assert row_id > 0

    async def test_get_trainer_includes_party(self):
        await init_db()
        await create_trainer(5002, "PokeFan2")
        p = make_pokemon(id_=4, name="charmander", types=["fire"])
        await save_pokemon_to_party(5002, p, slot=1)

        trainer = await get_trainer(5002)
        assert len(trainer.party) == 1
        assert trainer.party[0].name == "charmander"

    async def test_get_all_pokemon_empty(self):
        await init_db()
        await create_trainer(5003, "PokeFan3")
        result = await get_all_pokemon(5003)
        assert result == []

    async def test_get_all_pokemon_returns_all(self):
        await init_db()
        await create_trainer(5004, "PokeFan4")
        p1 = make_pokemon(id_=1, name="bulbasaur")
        p2 = make_pokemon(id_=4, name="charmander", types=["fire"])
        await save_pokemon_to_party(5004, p1, slot=1)
        await save_pokemon_to_party(5004, p2, slot=2)
        all_poke = await get_all_pokemon(5004)
        assert len(all_poke) == 2

    async def test_get_all_pokemon_includes_box_pokemon(self):
        """get_all_pokemon returns Pokémon regardless of party_slot."""
        await init_db()
        await create_trainer(5005, "PokeFan5")
        p_in_party = make_pokemon(id_=1, name="bulbasaur")
        p_in_box = make_pokemon(id_=4, name="charmander", types=["fire"])
        await save_pokemon_to_party(5005, p_in_party, slot=1)
        # slot=None means in box, not party
        await save_pokemon_to_party(5005, p_in_box, slot=None)
        all_poke = await get_all_pokemon(5005)
        assert len(all_poke) == 2

    async def test_update_pokemon(self):
        await init_db()
        await create_trainer(5006, "PokeFan6")
        p = make_pokemon(id_=25, name="pikachu")
        db_id = await save_pokemon_to_party(5006, p, slot=1)

        # Mutate and update
        p.db_id = db_id
        p.current_hp = 30
        p.level = 15
        p.xp = 200
        p.nickname = "Sparky"
        p.party_slot = 2
        await update_pokemon(p)

        trainer = await get_trainer(5006)
        updated = trainer.party[0]
        assert updated.current_hp == 30
        assert updated.level == 15
        assert updated.xp == 200
        assert updated.nickname == "Sparky"

    async def test_save_shiny_pokemon(self):
        await init_db()
        await create_trainer(5007, "Shiny Hunter")
        p = make_pokemon(id_=25, name="pikachu", is_shiny=True)
        await save_pokemon_to_party(5007, p, slot=1)

        trainer = await get_trainer(5007)
        assert trainer.party[0].is_shiny is True

    async def test_save_pokemon_with_multiple_moves(self):
        await init_db()
        await create_trainer(5008, "MoveMaster")
        moves = [
            make_move(name="Tackle", power=40),
            make_move(name="Growl", power=0, damage_class="status"),
            make_move(name="Flamethrower", type_="fire", power=90, damage_class="special"),
        ]
        p = make_pokemon(moves=moves)
        await save_pokemon_to_party(5008, p, slot=1)

        trainer = await get_trainer(5008)
        assert len(trainer.party[0].moves) == 3

    async def test_party_ordered_by_slot(self):
        await init_db()
        await create_trainer(5009, "OrderedTrainer")
        p1 = make_pokemon(id_=1, name="bulbasaur")
        p2 = make_pokemon(id_=4, name="charmander", types=["fire"])
        p3 = make_pokemon(id_=7, name="squirtle", types=["water"])
        # Insert in reverse slot order to check ORDER BY
        await save_pokemon_to_party(5009, p3, slot=3)
        await save_pokemon_to_party(5009, p1, slot=1)
        await save_pokemon_to_party(5009, p2, slot=2)

        trainer = await get_trainer(5009)
        assert trainer.party[0].name == "bulbasaur"
        assert trainer.party[1].name == "charmander"
        assert trainer.party[2].name == "squirtle"


# ── Encounters ────────────────────────────────────────────────────────────────

class TestEncounters:
    async def test_get_encounter_none_if_missing(self):
        await init_db()
        result = await get_encounter(8001)
        assert result is None

    async def test_save_and_get_encounter(self):
        await init_db()
        p = make_pokemon(id_=25, name="pikachu", types=["electric"], level=10)
        await save_encounter(8001, p)
        result = await get_encounter(8001)
        assert result is not None
        assert result.name == "pikachu"
        assert result.types == ["electric"]
        assert result.level == 10

    async def test_save_encounter_replace_existing(self):
        """save_encounter uses INSERT OR REPLACE."""
        await init_db()
        p1 = make_pokemon(id_=1, name="bulbasaur")
        p2 = make_pokemon(id_=4, name="charmander", types=["fire"])
        await save_encounter(8002, p1)
        await save_encounter(8002, p2)
        result = await get_encounter(8002)
        assert result.name == "charmander"

    async def test_update_encounter(self):
        await init_db()
        p = make_pokemon(id_=25, name="pikachu", types=["electric"])
        await save_encounter(8003, p)
        p.current_hp = 10
        await update_encounter(8003, p)
        result = await get_encounter(8003)
        assert result.current_hp == 10

    async def test_clear_encounter(self):
        await init_db()
        p = make_pokemon(id_=25, name="pikachu")
        await save_encounter(8004, p)
        await clear_encounter(8004)
        result = await get_encounter(8004)
        assert result is None

    async def test_clear_encounter_nonexistent_is_noop(self):
        await init_db()
        # Should not raise
        await clear_encounter(9999)

    async def test_encounter_preserves_shiny(self):
        await init_db()
        p = make_pokemon(is_shiny=True)
        await save_encounter(8005, p)
        result = await get_encounter(8005)
        assert result.is_shiny is True

    async def test_encounter_multiple_users(self):
        await init_db()
        p1 = make_pokemon(id_=1, name="bulbasaur")
        p2 = make_pokemon(id_=4, name="charmander", types=["fire"])
        await save_encounter(9001, p1)
        await save_encounter(9002, p2)
        r1 = await get_encounter(9001)
        r2 = await get_encounter(9002)
        assert r1.name == "bulbasaur"
        assert r2.name == "charmander"

    async def test_encounter_preserves_moves(self):
        await init_db()
        moves = [
            make_move(name="Thunder", type_="electric", power=110, pp=10),
            make_move(name="Quick Attack", power=40),
        ]
        p = make_pokemon(moves=moves)
        await save_encounter(8006, p)
        result = await get_encounter(8006)
        assert len(result.moves) == 2
        assert result.moves[0].name == "Thunder"
