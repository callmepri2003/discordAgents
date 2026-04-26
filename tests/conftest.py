from game.models import Move, Pokemon, Trainer


def make_move(
    name="Tackle",
    type_="normal",
    power=40,
    accuracy=100,
    pp=35,
    current_pp=35,
    damage_class="physical",
) -> Move:
    return Move(
        name=name,
        type=type_,
        power=power,
        accuracy=accuracy,
        pp=pp,
        current_pp=current_pp,
        damage_class=damage_class,
    )


def make_pokemon(
    *,
    id_=1,
    name="bulbasaur",
    types=None,
    level=10,
    hp=100,
    current_hp=None,
    attack=50,
    defense=50,
    sp_attack=50,
    sp_defense=50,
    speed=50,
    moves=None,
    is_shiny=False,
    nickname=None,
    catch_rate=45,
) -> Pokemon:
    if types is None:
        types = ["grass", "poison"]
    if moves is None:
        moves = [make_move()]
    if current_hp is None:
        current_hp = hp
    return Pokemon(
        id=id_,
        name=name,
        types=types,
        level=level,
        xp=0,
        max_hp=hp,
        current_hp=current_hp,
        attack=attack,
        defense=defense,
        sp_attack=sp_attack,
        sp_defense=sp_defense,
        speed=speed,
        moves=moves,
        sprite_url="https://example.com/sprite.png",
        catch_rate=catch_rate,
        is_shiny=is_shiny,
        nickname=nickname,
    )


def make_trainer(*, party=None) -> Trainer:
    t = Trainer(user_id=1, username="Ash")
    if party is not None:
        t.party = party
    return t
