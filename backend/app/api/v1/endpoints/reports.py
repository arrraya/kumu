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

    # Generate report
    report_data = report_generator.generate_full_report(player, team)

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
