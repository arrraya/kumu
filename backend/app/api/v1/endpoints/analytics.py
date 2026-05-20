"""
This module provides API endpoints for analytics.

It includes functions for running advanced analytics and predicting player performance.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas import analytics as analytics_schemas
import app.services.analytics_service as analytics_service


router = APIRouter()


@router.post("/advanced")
async def run_advanced_analytics(
    request: analytics_schemas.AdvancedAnalyticsRequest, db: Session = Depends(get_db)
):
    """Run advanced analytics."""
    try:
        # Inline the immediately returned variable
        return analytics_service.run_analysis(
            db,
            analysis_type=request.type,
            player_ids=request.player_ids,
            parameters=request.parameters,
        )
    except ValueError as e:
        # Explicitly raise from previous error
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/predict")
async def predict_performance(
    request: analytics_schemas.PredictionRequest, db: Session = Depends(get_db)
):
    """Predict player performance."""
    # Inline the immediately returned variable
    return analytics_service.predict_performance(
        db,
        player_id=request.player_id,
        team_id=request.team_id,
        horizon=request.horizon,
        factors=request.factors,
    )
