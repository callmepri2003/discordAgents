from dataclasses import dataclass, field

TYPE_EMOJI: dict[str, str] = {
    "normal": "⚪", "fire": "🔥", "water": "💧", "electric": "⚡",
    "grass": "🌿", "ice": "🧊", "fighting": "🥊", "poison": "☠️",
    "ground": "🌍", "flying": "🌬️", "psychic": "🔮", "bug": "🐛",
    "rock": "🪨", "ghost": "👻", "dragon": "🐉", "dark": "🌑",
    "steel": "⚙️", "fairy": "✨",
}

TYPE_COLORS: dict[str, int] = {
    "normal": 0xA8A878, "fire": 0xF08030, "water": 0x6890F0,
    "electric": 0xF8D030, "grass": 0x78C850, "ice": 0x98D8D8,
    "fighting": 0xC03028, "poison": 0xA040A0, "ground": 0xE0C068,
    "flying": 0xA890F0, "psychic": 0xF85888, "bug": 0xA8B820,
    "rock": 0xB8A038, "ghost": 0x705898, "dragon": 0x7038F8,
    "dark": 0x705848, "steel": 0xB8B8D0, "fairy": 0xEE99AC,
}


@dataclass
class Move:
    name: str
    type: str
    power: int
    accuracy: int
    pp: int
    current_pp: int
    damage_class: str  # "physical" | "special" | "status"


@dataclass
class Pokemon:
    id: int
    name: str
    types: list[str]
    level: int
    xp: int
    max_hp: int
    current_hp: int
    attack: int
    defense: int
    sp_attack: int
    sp_defense: int
    speed: int
    moves: list[Move]
    sprite_url: str
    catch_rate: int
    is_shiny: bool = False
    nickname: str | None = None
    db_id: int | None = None
    party_slot: int | None = None

    @property
    def display_name(self) -> str:
        return self.nickname or self.name.capitalize()

    @property
    def type_display(self) -> str:
        return " / ".join(
            f"{TYPE_EMOJI.get(t, '')} {t.capitalize()}" for t in self.types
        )

    @property
    def hp_percentage(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0.0

    def hp_bar(self, length: int = 12) -> str:
        filled = round(self.hp_percentage * length)
        if self.hp_percentage > 0.5:
            block = "🟩"
        elif self.hp_percentage > 0.25:
            block = "🟨"
        else:
            block = "🟥"
        return block * filled + "⬛" * (length - filled)

    def is_fainted(self) -> bool:
        return self.current_hp <= 0


@dataclass
class Trainer:
    user_id: int
    username: str
    pokeballs: int = 5
    great_balls: int = 0
    ultra_balls: int = 0
    potions: int = 3
    super_potions: int = 0
    party: list[Pokemon] = field(default_factory=list)

    @property
    def active_pokemon(self) -> Pokemon | None:
        for p in self.party:
            if not p.is_fainted():
                return p
        return None

    @property
    def has_pokeballs(self) -> bool:
        return self.pokeballs > 0 or self.great_balls > 0 or self.ultra_balls > 0
