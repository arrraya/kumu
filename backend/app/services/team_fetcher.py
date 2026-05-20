import httpx
from typing import List, Dict
from sqlalchemy.orm import Session
from app.db import models
import json

class TeamFetcher:
    def __init__(self):
        # Priority order of leagues as specified
        self.league_priority = [
            ("Premier League", "England"),
            ("La Liga", "Spain"),
            ("Serie A", "Italy"),
            ("Ligue 1", "France"),
            ("Bundesliga", "Germany"),
            ("Eredivisie", "Netherlands"),
            ("Süper Lig", "Turkey"),
            ("Superliga", "Denmark"),
            ("MLS", "USA"),
            ("Russian Premier League", "Russia")
        ]
        
    async def fetch_teams_for_player(self, player: models.Player, db: Session) -> List[Dict]:
        """
        Fetch teams dynamically based on player level
        Higher value players get top league teams
        """
        player_value = player.market_value or 10000000
        
        # Determine which leagues to search based on player value
        if player_value > 50000000:  # Top tier player
            leagues_to_search = self.league_priority[:3]  # Top 3 leagues
        elif player_value > 20000000:  # High tier
            leagues_to_search = self.league_priority[:5]  # Top 5 leagues
        elif player_value > 5000000:  # Mid tier
            leagues_to_search = self.league_priority[:7]  # Top 7 leagues
        else:  # Entry level
            leagues_to_search = self.league_priority  # All leagues
        
        teams = []
        for league_name, country in leagues_to_search:
            # Try to fetch from API or use default teams
            league_teams = await self._fetch_league_teams(league_name, country)
            teams.extend(league_teams)
            
        # Save to database for caching
        for team_data in teams:
            self._cache_team(db, team_data)
            
        return teams
    
    async def _fetch_league_teams(self, league: str, country: str) -> List[Dict]:
        """Fetch teams from a specific league"""
        # For now, return top teams from each league
        # This can be replaced with actual API calls
        
        league_teams = {
            "Premier League": [
                {"name": "Manchester City", "budget": 900000000, "style": "possession"},
                {"name": "Arsenal", "budget": 750000000, "style": "attacking"},
                {"name": "Liverpool", "budget": 700000000, "style": "gegenpressing"},
                {"name": "Manchester United", "budget": 650000000, "style": "counter-attack"},
                {"name": "Chelsea", "budget": 600000000, "style": "balanced"},
            ],
            "La Liga": [
                {"name": "Real Madrid", "budget": 800000000, "style": "balanced"},
                {"name": "Barcelona", "budget": 500000000, "style": "tiki-taka"},
                {"name": "Atlético Madrid", "budget": 400000000, "style": "defensive"},
            ],
            "Serie A": [
                {"name": "Inter Milan", "budget": 450000000, "style": "tactical"},
                {"name": "AC Milan", "budget": 400000000, "style": "counter-attack"},
                {"name": "Juventus", "budget": 500000000, "style": "balanced"},
            ],
            "Ligue 1": [
                {"name": "PSG", "budget": 700000000, "style": "attacking"},
                {"name": "Monaco", "budget": 300000000, "style": "balanced"},
            ],
            "Bundesliga": [
                {"name": "Bayern Munich", "budget": 650000000, "style": "high-pressing"},
                {"name": "Borussia Dortmund", "budget": 350000000, "style": "attacking"},
            ],
            "Eredivisie": [
                {"name": "Ajax", "budget": 150000000, "style": "youth-development"},
                {"name": "PSV", "budget": 120000000, "style": "attacking"},
            ],
            "MLS": [
                {"name": "Inter Miami", "budget": 100000000, "style": "star-focused"},
                {"name": "LA Galaxy", "budget": 90000000, "style": "attacking"},
            ]
        }
        
        teams = league_teams.get(league, [])
        
        # Format teams with full data
        formatted_teams = []
        for team in teams:
            formatted_teams.append({
                "name": team["name"],
                "league": league,
                "country": country,
                "budget": team["budget"],
                "formation": "4-3-3",
                "playing_style": {"style": team["style"], "tempo": "medium"},
                "requirements": {"positions": ["ST", "CM", "CB"], "age_range": [20, 32]}
            })
            
        return formatted_teams
    
    def _cache_team(self, db: Session, team_data: Dict):
        """Save team to database if not exists"""
        try:
            existing = db.query(models.Team).filter(
                models.Team.name == team_data["name"]
            ).first()
            
            if not existing:
                team = models.Team(
                    name=team_data["name"],
                    league=team_data["league"],
                    country=team_data["country"],
                    budget=team_data["budget"],
                    formation=team_data.get("formation", "4-3-3"),
                    playing_style=team_data.get("playing_style", {}),
                    requirements=team_data.get("requirements", {})
                )
                db.add(team)
                db.commit()
        except Exception as e:
            db.rollback()

team_fetcher = TeamFetcher()
