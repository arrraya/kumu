import httpx
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.db import models
import json
import asyncio

class DataSource:
    def __init__(self):
        import os
        self.api_football_key = os.getenv("API_FOOTBALL_KEY")
        self.use_statsbomb_free = False  # Set to True to use free data
        
    async def search_players_realtime(self, search: str) -> List[Dict]:
        """Search players from available data sources"""
        if self.api_football_key:
            results = await self._search_api_football(search)
            if results: 
                return results
            
        # Fallback to free API if API-Football fails
        return await self._search_free_backup(search)
    
    async def _search_api_football(self, search: str) -> List[Dict]:
        """API-Football via RapidAPI - correct endpoint"""
        if not self.api_football_key:
            return []
            
        headers = {
            "X-RapidAPI-Key": self.api_football_key,
            "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api-football-v1.p.rapidapi.com/v3/players",
                    params={"search": search},  # Removed season parameter
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    players = []
                    
                    for item in data.get("response", []):
                        player = item.get("player", {})
                        statistics = item.get("statistics", [{}])[0] if item.get("statistics") else {}
                        
                        players.append({
                            "name": player.get("name"),
                            "age": player.get("age"),
                            "nationality": player.get("nationality"),
                            "position": statistics.get("games", {}).get("position"),
                            "team": statistics.get("team", {}).get("name"),
                            "external_id": str(player.get("id")),
                            "market_value": 50000000  # Default value
                        })
                    
                    return players[:10]  # Return top 10 results
                    
        except Exception as e:
            print(f"API-Football error: {e}")
            
        return []
    
    async def _search_free_backup(self, search: str) -> List[Dict]:
        """Free backup API for testing"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php",
                    params={"p": search},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    players = []
                    
                    for player in data.get("player", [])[:5]:
                        players.append({
                            "name": player.get("strPlayer"),
                            "age": 2025 - int(player.get("dateBorn", "1990")[:4]),
                            "nationality": player.get("strNationality"),
                            "position": player.get("strPosition", "Unknown")[:3].upper(),
                            "team": player.get("strTeam"),
                            "external_id": player.get("idPlayer"),
                            "market_value": 10000000
                        })
                    
                    return players
                    
        except Exception as e:
            print(f"Free backup error: {e}")
            
        return []
    
    def cache_player_to_db(self, db: Session, player_data: Dict):
        """Save player to database if not exists"""
        try:
            if not player_data.get("external_id"):
                return
                
            existing = db.query(models.Player).filter(
                models.Player.external_id == player_data["external_id"]
            ).first()
            
            if not existing:
                player = models.Player(
                    external_id=player_data.get("external_id"),
                    name=player_data.get("name"),
                    age=player_data.get("age", 25),
                    position=player_data.get("position", "CM"),
                    nationality=player_data.get("nationality", "Unknown"),
                    current_team=player_data.get("team", "Free Agent"),
                    market_value=player_data.get("market_value", 10000000),
                    performance_index={
                        "value": 75,
                        "trend": 0,
                        "volatility": 0.5,
                        "confidence": 0.7
                    },
                    metrics={}
                )
                db.add(player)
                db.commit()
        except Exception as e:
            print(f"Cache error: {e}")
            db.rollback()

data_source = DataSource()
