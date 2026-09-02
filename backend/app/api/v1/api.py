from fastapi import APIRouter
from app.api.v1.endpoints import auth, players, teams, matches, reports, analytics, market

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(players.router, prefix="/players", tags=["players"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(matches.router, prefix="/matches", tags=["matches"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(market.router, prefix="/market", tags=["market"])
