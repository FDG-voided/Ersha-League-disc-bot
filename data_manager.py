import json
import os
import asyncio
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PLAYERS_PATH = os.path.join(DATA_DIR, "players.json")
CLUBS_PATH = os.path.join(DATA_DIR, "clubs.json")
PENDING_OFFERS_PATH = os.path.join(DATA_DIR, "pending_offers.json")


def calculate_rating(goals: int, assists: int) -> int:
    base = 50
    goal_contribution = goals * 2.5
    assist_contribution = assists * 1.8
    combined = base + goal_contribution + assist_contribution
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


async def _read_json(path: str) -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_json_sync, path)


def _read_json_sync(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _write_json(path: str, data: list) -> None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _write_json_sync, path, data)


def _write_json_sync(path: str, data: list) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def load_players() -> list:
    return await _read_json(PLAYERS_PATH)


async def save_players(players: list) -> None:
    await _write_json(PLAYERS_PATH, players)


async def load_clubs() -> list:
    return await _read_json(CLUBS_PATH)


async def save_clubs(clubs: list) -> None:
    await _write_json(CLUBS_PATH, clubs)


async def load_pending_offers() -> list:
    return await _read_json(PENDING_OFFERS_PATH)


async def save_pending_offers(offers: list) -> None:
    await _write_json(PENDING_OFFERS_PATH, offers)


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
        p["rating"] = calculate_rating(p.get("goals", 0), p.get("assists", 0))
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
