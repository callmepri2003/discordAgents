# discordAgents — Pokémon Discord Bot

> A text-based Pokémon RPG playable entirely inside Discord. Battle wild Pokémon, catch them, explore areas, and level up your team — all through slash commands.

---

## What it does

| Command | Description |
|---|---|
| `/start` | Begin your journey and pick a starter Pokémon |
| `/battle` | Encounter a wild Pokémon and fight |
| `/catch` | Throw a Poké Ball at a weakened wild Pokémon |
| `/explore` | Discover new areas and trigger random encounters |
| `/party` | View your current team |

## How it works

The battle engine implements the **Gen 5 damage formula** with the complete 18-type effectiveness chart — including immunities (Ghost → Normal, Ground → Flying, Dragon → Fairy). Every matchup computes the correct multiplier from first principles.

Pokémon data (base stats, move sets, types) is pulled live from the [PokéAPI](https://pokeapi.co) — no hardcoded Pokédex required.

Player progress (caught Pokémon, party, levels) is persisted in an async SQLite database between sessions.

## Tech stack

| Layer | Technology |
|---|---|
| Bot framework | discord.py 2.3+ |
| HTTP client | aiohttp (async) |
| Database | aiosqlite (async SQLite) |
| Data source | PokéAPI (free, no auth required) |
| Architecture | discord.py Cogs — `game`, `exploration` |
| Tests | pytest |

## Project structure

```
bot.py                  # Entry point — loads cogs and starts the bot
cogs/
├── game.py             # Battle and catch slash commands
└── exploration.py      # Explore and encounter slash commands
game/
├── battle_engine.py    # Gen 5 damage formula + 18-type chart
├── catch_engine.py     # Catch rate calculation
├── pokeapi.py          # Async PokéAPI client
├── database.py         # SQLite persistence layer
├── models.py           # Pokémon / Move data classes
└── embeds.py           # Discord embed builders
tests/                  # Test suite
```

## Local setup

```bash
git clone https://github.com/callmepri2003/discordAgents
cd discordAgents
pip install -r requirements.txt

# Create a bot at discord.com/developers, then:
echo "DISCORD_TOKEN=your_token_here" > .env

python bot.py
```

Requires Python 3.11+. Create a bot application at [discord.com/developers/applications](https://discord.com/developers/applications) and invite it to your server with the `bot` and `applications.commands` scopes.
