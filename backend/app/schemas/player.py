from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime

class PerformanceIndex(BaseModel):
    value: float = Field(default=75.0)
    trend: float = Field(default=0.0)
    volatility: float = Field(default=0.5)
    confidence: float = Field(default=0.7)

class Player(BaseModel):
    id: Optional[int] = None
    external_id: Optional[str] = None
    name: str
    age: int
    position: str  # Accepts any position string
    nationality: str
    current_team: Optional[str] = None
    market_value: float = Field(default=10000000)
    performance_index: Optional[PerformanceIndex] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    performance_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @field_validator('performance_history', mode='before')
    @classmethod
    def validate_performance_history(cls, v):
        if v is None:
            return []
        return v
    
    @field_validator('metrics', mode='before')
    @classmethod
    def validate_metrics(cls, v):
        if v is None:
            return {}
        return v
    
    class Config:
        from_attributes = True

class PlayerDetail(Player):
    """Detailed player view - same as Player for now"""
    pass

class PlayerCreate(BaseModel):
    name: str
    age: int
    position: str
    nationality: str
    current_team: Optional[str] = None
    market_value: Optional[float] = 10000000

class PlayerUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    position: Optional[str] = None
    nationality: Optional[str] = None
    current_team: Optional[str] = None
    market_value: Optional[float] = None
