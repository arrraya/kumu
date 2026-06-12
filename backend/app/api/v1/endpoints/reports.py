from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.schemas import report as report_schemas
from app.services.scouting_report_generator import ScoutingReportGenerator
from app.services.pdf_generator import PDFReportGenerator
import app.services.player_service as player_service
import app.services.team_service as team_service

router = APIRouter()
report_generator = ScoutingReportGenerator()
pdf_generator = PDFReportGenerator()


@router.post("/generate", response_model=report_schemas.ScoutingReport)
async def generate_report(
    request: report_schemas.GenerateReportRequest, db: Session = Depends(get_db)
):
    """Generate a scouting report"""
    # Get player and team data
    player = player_service.get_player(db, int(request.player_id))
    team = team_service.get_team(db, int(request.team_id))

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Convert ORM models to dicts expected by the report generator
    player_data = {
        "id": player.id,
        "name": player.name,
        "age": player.age,
        "position": player.position,
        "nationality": player.nationality,
        "current_team": getattr(player, "current_team", None),
        "market_value": getattr(player, "market_value", 0) or 0,
        "performance_index": getattr(player, "performance_index", None)
        or {"value": 70.0, "trend": 0.0, "volatility": 0.2, "confidence": 0.5},
        "metrics": getattr(player, "metrics", None)
        or {
            "passing": {
                "completion_rate": 0.75,
                "progressive_passes_per_90": 3.0,
                "key_passes_per_90": 1.5,
                "pass_difficulty_score": 0.6,
            },
            "shooting": {
                "shots_per_90": 1.5,
                "xG_per_shot": 0.12,
                "conversion_rate": 0.12,
                "goals_per_90": 0.2,
                "assists_per_90": 0.2,
            },
            "movement": {
                "distance_covered_per_90": 10.0,
                "high_intensity_runs": 20,
                "average_speed": 7.0,
            },
            "defensive": {
                "tackles_per_90": 1.5,
                "interceptions_per_90": 1.5,
                "aerial_duels_won": 0.5,
            },
        },
        "performance_history": getattr(player, "performance_history", None)
        or [{"rating": 7.0, "goals": 0, "assists": 0}] * 5,
    }
    team_data = {
        "id": team.id,
        "name": team.name,
        "league": getattr(team, "league", None),
        "country": getattr(team, "country", None),
        "budget": getattr(team, "budget", 0) or 0,
        "formation": getattr(team, "formation", None),
        "playing_style": getattr(team, "playing_style", None) or {},
    }

    # Generate report
    report_data = report_generator.generate_full_report(player_data, team_data)

    # Save report to database
    db_report = models.ScoutingReport(
        player_id=request.player_id,
        team_id=request.team_id,
        match_id=request.match_id,
        report_data=report_data,
    )
    db.add(db_report)
    db.commit()

    return report_data


@router.get("/{report_id}", response_model=report_schemas.ScoutingReport)
def get_report(report_id: int, db: Session = Depends(get_db)):
    """Get an existing scouting report"""
    report = db.query(models.ScoutingReport).filter(models.ScoutingReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report.report_data


@router.get("/{report_id}/pdf")
@router.post("/{report_id}/pdf")
def export_report_pdf(report_id: int, db: Session = Depends(get_db)):
    """Export a scouting report as PDF (supports both GET and POST)"""
    report = db.query(models.ScoutingReport).filter(models.ScoutingReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Generate PDF from report data
    pdf_buffer = pdf_generator.generate_pdf(report.report_data)

    # Get player name for filename
    player_name = report.report_data.get("report_metadata", {}).get("player_name", "report")
    filename = f"scouting_report_{player_name.replace(' ', '_')}_{report_id}.pdf"

    # Return PDF as streaming response
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.post("/{report_id}")
def export_report_pdf_short(report_id: int, db: Session = Depends(get_db)):
    """Export a scouting report as PDF via POST /api/v1/reports/{report_id}"""
    report = db.query(models.ScoutingReport).filter(models.ScoutingReport.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Generate PDF from report data
    pdf_buffer = pdf_generator.generate_pdf(report.report_data)

    # Get player name for filename
    player_name = report.report_data.get("report_metadata", {}).get("player_name", "report")
    filename = f"scouting_report_{player_name.replace(' ', '_')}_{report_id}.pdf"

    # Return PDF as streaming response
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
