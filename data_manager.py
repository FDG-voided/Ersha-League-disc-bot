import json
import os
import sqlite3
import aiosqlite
from typing import Optional
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PLAYERS_PATH = os.path.join(DATA_DIR, "players.json")
CLUBS_PATH = os.path.join(DATA_DIR, "clubs.json")
PENDING_OFFERS_PATH = os.path.join(DATA_DIR, "pending_offers.json")
DB_PATH = os.path.join(DATA_DIR, "ersha_league.db")


POSITION_WEIGHTS = {
    "GK":  {"goals": 5.0, "assists": 4.0},
    "CB":  {"goals": 4.5, "assists": 3.5},
    "LB":  {"goals": 4.0, "assists": 3.5},
    "RB":  {"goals": 4.0, "assists": 3.5},
    "CM":  {"goals": 3.5, "assists": 2.5},
    "CAM": {"goals": 3.0, "assists": 2.2},
    "LM":  {"goals": 3.0, "assists": 2.5},
    "RM":  {"goals": 3.0, "assists": 2.5},
    "LW":  {"goals": 2.5, "assists": 2.0},
    "RW":  {"goals": 2.5, "assists": 2.0},
    "ST":  {"goals": 2.5, "assists": 1.8},
    "CF":  {"goals": 2.5, "assists": 1.8},
}


def calculate_rating(goals: int, assists: int, position: str = "Unknown") -> int:
    w = POSITION_WEIGHTS.get(position, {"goals": 2.5, "assists": 1.8})
    base = 50
    combined = base + goals * w["goals"] + assists * w["assists"]
    raw = round(combined)
    if raw < 50:
        return 50
    return min(99, raw)


def get_rating_tier(rating: int) -> str:
    if rating >= 85:
        return "elite"
    if rating >= 75:
        return "gold"
    if rating >= 65:
        return "silver"
    return "bronze"


def get_embed_color(rating: int) -> int:
    if rating >= 85:
        return 0x00CED1
    if rating >= 75:
        return 0xFFD700
    if rating >= 65:
        return 0xC0C0C0
    return 0x8B7355


def _dict_to_row(player: dict) -> tuple:
    return (
        player["id"],
        player.get("discord_id", ""),
        player.get("name", ""),
        player.get("club_id", ""),
        player.get("nationality", "Unknown"),
        player.get("position", "Unknown"),
        player.get("age", 25),
        player.get("goals", 0),
        player.get("assists", 0),
        player.get("rating", 50),
        player.get("rating_tier", "bronze"),
    )


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "discord_id": row[1],
        "name": row[2],
        "club_id": row[3] if row[3] else None,
        "nationality": row[4],
        "position": row[5],
        "age": row[6],
        "goals": row[7],
        "assists": row[8],
        "rating": row[9],
        "rating_tier": row[10],
    }


def _club_to_row(club: dict) -> tuple:
    return (
        club["id"],
        club.get("name", ""),
        club.get("owner_discord_id", ""),
        json.dumps(club.get("players", [])),
        club.get("funds", 0),
    )


def _row_to_club(row: tuple) -> dict:
    return {
        "id": row[0],
        "name": row[1],
        "owner_discord_id": row[2],
        "players": json.loads(row[3]) if row[3] else [],
        "funds": row[4] if len(row) > 4 else 0,
    }


def _offer_to_row(offer: dict) -> tuple:
    return (
        offer["id"],
        offer.get("player_id", ""),
        offer.get("player_name", ""),
        offer.get("from_club_id", ""),
        offer.get("from_club_name", ""),
        offer.get("to_club_id", ""),
        offer.get("to_club_name", ""),
        offer.get("amount", 0),
        offer.get("status", "pending"),
        offer.get("created_at", ""),
    )


def _row_to_offer(row: tuple) -> dict:
    return {
        "id": row[0],
        "player_id": row[1],
        "player_name": row[2],
        "from_club_id": row[3],
        "from_club_name": row[4],
        "to_club_id": row[5],
        "to_club_name": row[6],
        "amount": row[7],
        "status": row[8],
        "created_at": row[9],
    }


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    discord_id TEXT DEFAULT '',
    name TEXT NOT NULL,
    club_id TEXT DEFAULT '',
    nationality TEXT DEFAULT 'Unknown',
    position TEXT DEFAULT 'Unknown',
    age INTEGER DEFAULT 25,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 50,
    rating_tier TEXT DEFAULT 'bronze'
);

CREATE TABLE IF NOT EXISTS clubs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    owner_discord_id TEXT DEFAULT '',
    players TEXT DEFAULT '[]',
    funds INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pending_offers (
    id TEXT PRIMARY KEY,
    player_id TEXT DEFAULT '',
    player_name TEXT DEFAULT '',
    from_club_id TEXT DEFAULT '',
    from_club_name TEXT DEFAULT '',
    to_club_id TEXT DEFAULT '',
    to_club_name TEXT DEFAULT '',
    amount INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT ''
);
"""


class Database:
    def __init__(self):
        self.db: Optional[aiosqlite.Connection] = None
        self.use_sqlite = False

    async def connect(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            self.db = await aiosqlite.connect(DB_PATH)
            self.db.row_factory = sqlite3.Row
            await self.db.executescript(SCHEMA_SQL)
            await self.db.executescript("ALTER TABLE clubs ADD COLUMN funds INTEGER DEFAULT 0")
            await self.db.commit()
            self.use_sqlite = True
            print(f"✅ SQLite database at {DB_PATH}")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ SQLite unavailable ({e}), using JSON file storage")
                self.use_sqlite = False
            else:
                await self.db.commit()
                self.use_sqlite = True

    async def load_players(self) -> list:
        if self.use_sqlite:
            cursor = await self.db.execute("SELECT * FROM players")
            rows = await cursor.fetchall()
            return [_row_to_dict(r) for r in rows]
        return await _read_json(PLAYERS_PATH)

    async def save_players(self, players: list) -> None:
        if self.use_sqlite:
            await self.db.executemany(
                "INSERT OR REPLACE INTO players VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [_dict_to_row(p) for p in players],
            )
            await self.db.commit()
            return
        await _write_json(PLAYERS_PATH, players)

    async def load_clubs(self) -> list:
        if self.use_sqlite:
            cursor = await self.db.execute("SELECT * FROM clubs")
            rows = await cursor.fetchall()
            return [_row_to_club(r) for r in rows]
        return await _read_json(CLUBS_PATH)

    async def save_clubs(self, clubs: list) -> None:
        if self.use_sqlite:
            await self.db.executemany(
                "INSERT OR REPLACE INTO clubs VALUES (?,?,?,?,?)",
                [_club_to_row(c) for c in clubs],
            )
            await self.db.commit()
            return
        await _write_json(CLUBS_PATH, clubs)

    async def load_pending_offers(self) -> list:
        if self.use_sqlite:
            cursor = await self.db.execute("SELECT * FROM pending_offers")
            rows = await cursor.fetchall()
            return [_row_to_offer(r) for r in rows]
        return await _read_json(PENDING_OFFERS_PATH)

    async def save_pending_offers(self, offers: list) -> None:
        if self.use_sqlite:
            await self.db.executemany(
                "INSERT OR REPLACE INTO pending_offers VALUES (?,?,?,?,?,?,?,?,?,?)",
                [_offer_to_row(o) for o in offers],
            )
            await self.db.commit()
            return
        await _write_json(PENDING_OFFERS_PATH, offers)


db = Database()


async def init_db():
    await db.connect()


async def load_players() -> list:
    return await db.load_players()


async def save_players(players: list) -> None:
    await db.save_players(players)


async def load_clubs() -> list:
    return await db.load_clubs()


async def save_clubs(clubs: list) -> None:
    await db.save_clubs(clubs)


async def load_pending_offers() -> list:
    return await db.load_pending_offers()


async def save_pending_offers(offers: list) -> None:
    await db.save_pending_offers(offers)


async def get_player_by_id(pid: str) -> Optional[dict]:
    players = await load_players()
    for p in players:
        if p["id"] == pid:
            return p
    return None


async def get_club_by_id(cid: str) -> Optional[dict]:
    clubs = await load_clubs()
    for c in clubs:
        if c["id"] == cid:
            return c
    return None


async def get_club_by_owner(discord_id: str) -> Optional[dict]:
    clubs = await load_clubs()
    for c in clubs:
        if str(c["owner_discord_id"]) == str(discord_id):
            return c
    return None


def get_club_by_owner_sync(discord_id: str) -> Optional[dict]:
    clubs = _read_json_sync(CLUBS_PATH)
    for c in clubs:
        if str(c["owner_discord_id"]) == str(discord_id):
            return c
    return None


async def recalculate_player_ratings() -> None:
    players = await load_players()
    for p in players:
        p["rating"] = calculate_rating(p.get("goals", 0), p.get("assists", 0), p.get("position", "Unknown"))
        p["rating_tier"] = get_rating_tier(p["rating"])
    await save_players(players)


async def transfer_player(player_id: str, to_club_id: str) -> None:
    players = await load_players()
    old_club_id = None
    for p in players:
        if p["id"] == player_id:
            old_club_id = p.get("club_id")
            p["club_id"] = to_club_id
            break
    await save_players(players)
    clubs = await load_clubs()
    for c in clubs:
        if old_club_id and c["id"] == old_club_id and player_id in c["players"]:
            c["players"].remove(player_id)
        if c["id"] == to_club_id and player_id not in c["players"]:
            c["players"].append(player_id)
    await save_clubs(clubs)


async def add_player_to_club(club_id: str, player_id: str) -> None:
    clubs = await load_clubs()
    for c in clubs:
        if c["id"] == club_id:
            if player_id not in c["players"]:
                c["players"].append(player_id)
            break
    await save_clubs(clubs)
    players = await load_players()
    for p in players:
        if p["id"] == player_id:
            p["club_id"] = club_id
            break
    await save_players(players)


async def remove_player_from_club(player_id: str) -> None:
    players = await load_players()
    player_club_id = None
    for p in players:
        if p["id"] == player_id and p["club_id"] is not None:
            player_club_id = p["club_id"]
            p["club_id"] = None
            break
    await save_players(players)
    if player_club_id:
        clubs = await load_clubs()
        for c in clubs:
            if c["id"] == player_club_id and player_id in c["players"]:
                c["players"].remove(player_id)
                break
        await save_clubs(clubs)


async def _read_json(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _write_json(path: str, data: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json_sync(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json_sync(path: str, data: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
