# Ersha League Bot

A Discord bot for managing a football/soccer league, with a companion stat-input website.

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the bot

Edit `.env` in the project root:

- `TOKEN` — Your Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications)
- `GUILD_ID` — The Discord server (guild) ID where the bot will operate
- `OWNER_1_ID` — Discord user ID of the first club owner
- `OWNER_2_ID` — Discord user ID of the second club owner

Replace `OWNER_1_ID` and `OWNER_2_ID` in `.env` with real Discord user IDs (right-click a user in Discord → Copy ID — requires Developer Mode enabled in Discord settings).

### 3. Run the bot

```bash
python bot.py
```

The bot will sync all slash commands to your guild and recalculate player ratings on startup.

### 4. Discord Permissions

When inviting the bot, ensure it has these OAuth2 scopes:
- `bot`
- `applications.commands`

Required bot permissions:
- Send Messages
- Embed Links
- Read Message History
- Use Slash Commands

## Bot Commands

| Command | Description | Who Can Use |
|---|---|---|
| `/review <name>` | View a FIFA-style player card | Anyone |
| `/leaderboard [type]` | Top 10 by goals, assists, or rating | Anyone |
| `/club <name>` | View club details and squad | Anyone |
| `/myclub` | View your own club | Club owners |
| `/free_agents` | List all free agent players | Anyone |
| `/buy <name>` | Buy a free agent for your club | Club owners |
| `/sell <name>` | Release a player from your club | Club owners |
| `/offer <name> @owner <fee>` | Propose a transfer to another club | Club owners |
| `/accept_offer <name>` | Accept a pending transfer offer | Club owners |
| `/reject_offer <name>` | Reject a pending transfer offer | Club owners |
| `/add_player <name> <position> <nationality>` | Add a new free agent player | League Admin or guild owner |

## Stat-Input Website

Open `stats.html` in a browser to view and edit player statistics.

### Features:
- Dark football-pitch themed UI with gold accents
- Table of all players with inline-editable Goals and Assists
- "Recalculate" button per row to apply the rating equation
- "Recalculate All" to update all ratings at once
- Search/filter by player name or club
- Colored rating badges (bronze / silver / gold / elite)
- "Save All" downloads an updated `players.json` file

### Usage

**Option A — HTTP server (recommended):**
```bash
cd /path/to/ersha-league-bot
python3 -m http.server 8000
```
Then open `http://localhost:8000/stats.html` in your browser. The page automatically reads the live `data/players.json` and `data/clubs.json` files.

**Option B — File picker (works from `file://`):**
Open `stats.html` directly in your browser. Since `file://` blocks `fetch()`, use the **"Load Players"** and **"Load Clubs"** buttons to manually select your JSON files from the `data/` folder.

After editing stats, use **"Save All"** to download the updated `players.json`, then replace `data/players.json` with the downloaded file.

## Rating Equation

```
base = 50
goal_contribution = goals * 2.5
assist_contribution = assists * 1.8
rating = min(99, max(50, round(base + goal_contribution + assist_contribution)))
```

## File Structure

```
ersha-league-bot/
├── bot.py                  # Main bot entry point
├── config.py               # Configuration (reads from .env)
├── data_manager.py         # JSON I/O, rating equation, helpers
├── cogs/
│   ├── __init__.py
│   ├── player_commands.py  # /review, /leaderboard, /free_agents, /add_player
│   ├── club_commands.py    # /club, /myclub, /buy, /sell
│   └── transfer_commands.py # /offer, /accept_offer, /reject_offer
├── data/
│   ├── players.json        # Player records
│   ├── clubs.json          # Club records
│   └── pending_offers.json # Pending transfer offers
├── stats.html              # Stat-input website
├── requirements.txt        # Python dependencies
├── .env                    # Bot configuration (not tracked)
└── README.md               # This file
```
# Ersha-League-disc-bot
