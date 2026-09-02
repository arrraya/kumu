from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Organization(Base):
    """A tenant. Either the public reference dataset or a paying client.

    The public organisation is what keeps the demo alive after login exists,
    and it is the population every client's percentiles are measured against
    before they have data of their own.
    """

    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)
    kind = Column(String, nullable=False, default="client")  # public | client
    # Consent for the aggregate benchmark, off unless explicitly granted.
    allows_aggregate = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")

    @property
    def is_public(self) -> bool:
        return self.kind == "public"


class User(Base):
    """A person, always belonging to an organisation.

    Modelled as organisation-first on purpose: a club is several people sharing
    one dataset, and retrofitting that onto standalone users means migrating
    every row later.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, nullable=False, default="member")  # owner | member
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    # Owner of this row. Denormalised onto every table on purpose: the
    # raw SQL queries in the matcher and generator bypass ORM filters,
    # so each one must be able to scope directly.
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
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
    # Owner of this row. Denormalised onto every table on purpose: the
    # raw SQL queries in the matcher and generator bypass ORM filters,
    # so each one must be able to scope directly.
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    external_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    league = Column(String)
    country = Column(String)
    budget = Column(Float)
    formation = Column(String)
    # "club" or "national": national sides hold real squads from the source
    # data, but only clubs are valid transfer destinations.
    team_type = Column(String, default="club")
    playing_style = Column(JSON)
    requirements = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    matches = relationship("PlayerTeamMatch", back_populates="team")
    reports = relationship("ScoutingReport", back_populates="team")


class SquadMembership(Base):
    """Who belongs to which team.

    Squad lookups used to compare players.current_team to the team name as
    strings, so no club ever resolved a squad. `source` records where each link
    came from — national (real, from the source data), user (assembled in the
    app) or api (a future provider) — so all three can coexist in one relation.
    """

    __tablename__ = "squad_memberships"

    id = Column(Integer, primary_key=True, index=True)
    # Owner of this row. Denormalised onto every table on purpose: the
    # raw SQL queries in the matcher and generator bypass ORM filters,
    # so each one must be able to scope directly.
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    player_id = Column(Integer, ForeignKey("players.id"), index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), index=True)
    source = Column(String, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)

    player = relationship("Player")
    team = relationship("Team")


class PlayerTeamMatch(Base):
    __tablename__ = "player_team_matches"

    id = Column(Integer, primary_key=True, index=True)
    # Owner of this row. Denormalised onto every table on purpose: the
    # raw SQL queries in the matcher and generator bypass ORM filters,
    # so each one must be able to scope directly.
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
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
    # Owner of this row. Denormalised onto every table on purpose: the
    # raw SQL queries in the matcher and generator bypass ORM filters,
    # so each one must be able to scope directly.
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    match_id = Column(Integer, ForeignKey("player_team_matches.id"))
    report_data = Column(JSON)
    generated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    player = relationship("Player", back_populates="reports")
    team = relationship("Team", back_populates="reports")
