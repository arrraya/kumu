from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    age = Column(Integer)
    position = Column(String)
    nationality = Column(String)
    current_team = Column(String)
    market_value = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # JSON fields for complex data
    performance_index = Column(JSON)
    metrics = Column(JSON)
    performance_history = Column(JSON)

    # Relationships
    matches = relationship("PlayerTeamMatch", back_populates="player")
    reports = relationship("ScoutingReport", back_populates="player")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    league = Column(String)
    country = Column(String)
    budget = Column(Float)
    formation = Column(String)
    playing_style = Column(JSON)
    requirements = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    matches = relationship("PlayerTeamMatch", back_populates="team")
    reports = relationship("ScoutingReport", back_populates="team")


class PlayerTeamMatch(Base):
    __tablename__ = "player_team_matches"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    match_score = Column(Float)
    score_breakdown = Column(JSON)
    calculated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    player = relationship("Player", back_populates="matches")
    team = relationship("Team", back_populates="matches")


class ScoutingReport(Base):
    __tablename__ = "scouting_reports"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    match_id = Column(Integer, ForeignKey("player_team_matches.id"))
    report_data = Column(JSON)
    generated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    player = relationship("Player", back_populates="reports")
    team = relationship("Team", back_populates="reports")
