import sys
import os
import json
import uvicorn
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import data_manager as dm

app = FastAPI(title="Ersha League Admin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class PlayerIn(BaseModel):
    name: str
    club_id: Optional[str] = None
    nationality: str = "Unknown"
    position: str = "Unknown"
    age: int = 25
    goals: int = 0
    assists: int = 0


class PlayerOut(PlayerIn):
    id: str
    rating: int
    rating_tier: str


class ClubIn(BaseModel):
    name: str
    owner_discord_id: str = "0"
    funds: int = 0


class ClubOut(ClubIn):
    id: str
    players: list[str] = []


@app.on_event("startup")
async def startup():
    await dm.init_db()


@app.get("/")
async def index():
    return FileResponse(os.path.join(SCRIPT_DIR, "stats.html"))


@app.get("/api/players")
async def list_players():
    return await dm.load_players()


@app.get("/api/players/{player_id}")
async def get_player(player_id: str):
    p = await dm.get_player_by_id(player_id)
    if not p:
        raise HTTPException(404, "Player not found")
    return p


@app.post("/api/players")
async def create_player(data: PlayerIn):
    players = await dm.load_players()
    pid = str(uuid4())
    rating = dm.calculate_rating(data.goals, data.assists, data.position)
    player = {
        "id": pid,
        "name": data.name,
        "club_id": data.club_id,
        "nationality": data.nationality,
        "position": data.position,
        "age": data.age,
        "goals": data.goals,
        "assists": data.assists,
        "rating": rating,
        "rating_tier": dm.get_rating_tier(rating),
    }
    players.append(player)
    await dm.save_players(players)
    if data.club_id:
        await dm.add_player_to_club(data.club_id, pid)
    return player


@app.put("/api/players/{player_id}")
async def update_player(player_id: str, data: PlayerIn):
    players = await dm.load_players()
    for i, p in enumerate(players):
        if p["id"] == player_id:
            old_club = p.get("club_id")
            rating = dm.calculate_rating(data.goals, data.assists, data.position)
            players[i].update({
                "name": data.name,
                "club_id": data.club_id,
                "nationality": data.nationality,
                "position": data.position,
                "age": data.age,
                "goals": data.goals,
                "assists": data.assists,
                "rating": rating,
                "rating_tier": dm.get_rating_tier(rating),
            })
            await dm.save_players(players)
            if old_club != data.club_id:
                if old_club:
                    await dm.remove_player_from_club(player_id)
                if data.club_id:
                    await dm.add_player_to_club(data.club_id, player_id)
            return players[i]
    raise HTTPException(404, "Player not found")


@app.delete("/api/players/{player_id}")
async def delete_player(player_id: str):
    players = await dm.load_players()
    removed = [p for p in players if p["id"] == player_id]
    if not removed:
        raise HTTPException(404, "Player not found")
    players = [p for p in players if p["id"] != player_id]
    await dm.save_players(players)
    await dm.remove_player_from_club(player_id)
    return {"ok": True, "deleted": removed[0]}


@app.api_route("/api/players/batch", methods=["PUT"])
async def replace_all_players(players: list[dict]):
    for p in players:
        p["rating"] = dm.calculate_rating(p.get("goals", 0), p.get("assists", 0), p.get("position", "Unknown"))
        p["rating_tier"] = dm.get_rating_tier(p["rating"])
    await dm.save_players(players)
    return {"ok": True, "count": len(players)}


@app.get("/api/clubs")
async def list_clubs():
    return await dm.load_clubs()


@app.put("/api/clubs/set-funds")
async def set_all_club_funds(data: dict):
    amount = data.get("amount", 0)
    clubs = await dm.load_clubs()
    for c in clubs:
        c["funds"] = amount
    await dm.save_clubs(clubs)
    return {"ok": True, "amount": amount, "clubs_updated": len(clubs)}


@app.get("/api/clubs/{club_id}")
async def get_club(club_id: str):
    c = await dm.get_club_by_id(club_id)
    if not c:
        raise HTTPException(404, "Club not found")
    players = await dm.load_players()
    club_players = [p for p in players if p.get("club_id") == club_id]
    return {**c, "player_details": club_players}


@app.post("/api/clubs")
async def create_club(data: ClubIn):
    clubs = await dm.load_clubs()
    cid = str(uuid4())
    club = {
        "id": cid,
        "name": data.name,
        "owner_discord_id": data.owner_discord_id,
        "players": [],
        "funds": data.funds,
    }
    clubs.append(club)
    await dm.save_clubs(clubs)
    return club


@app.put("/api/clubs/{club_id}")
async def update_club(club_id: str, data: ClubIn):
    clubs = await dm.load_clubs()
    for i, c in enumerate(clubs):
        if c["id"] == club_id:
            clubs[i]["name"] = data.name
            clubs[i]["owner_discord_id"] = data.owner_discord_id
            clubs[i]["funds"] = data.funds
            await dm.save_clubs(clubs)
            return clubs[i]
    raise HTTPException(404, "Club not found")


@app.delete("/api/clubs/{club_id}")
async def delete_club(club_id: str):
    clubs = await dm.load_clubs()
    removed = [c for c in clubs if c["id"] == club_id]
    if not removed:
        raise HTTPException(404, "Club not found")
    clubs = [c for c in clubs if c["id"] != club_id]
    await dm.save_clubs(clubs)
    players = await dm.load_players()
    for p in players:
        if p.get("club_id") == club_id:
            p["club_id"] = None
    await dm.save_players(players)
    return {"ok": True, "deleted": removed[0]}


@app.get("/api/pending-offers")
async def list_offers():
    return await dm.load_pending_offers()


def main():
    port = int(os.getenv("ADMIN_PORT", "8000"))
    host = os.getenv("ADMIN_HOST", "0.0.0.0")
    print(f"🚀 Admin panel at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
