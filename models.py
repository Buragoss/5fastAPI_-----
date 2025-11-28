from pydantic import BaseModel, Field
from typing import Optional, Literal, List

class SessionEnd(BaseModel):
    status: Literal["completed", "error"] = Field("completed", example="completed")

class SensorReading(BaseModel):
    sensor_type: str = Field(..., min_length=1, max_length=50, example="pressure")
    value: float = Field(..., example=68.4)
    unit: str = Field("", max_length=20, example="bar")

class ActuatorCommand(BaseModel):
    actuator_type: str = Field(..., min_length=1, max_length=50, example="movement")
    command: float = Field(..., example=1.0)
    status: str = Field("sent", max_length=50, example="ВПРАВО → (3,2)")

class EventLog(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=50, example="leak_detected")
    severity: Literal["info", "warning", "error"] = Field(..., example="error")
    message: str = Field(..., min_length=1, max_length=500, example="УТЕЧКА в точке (4,2): 32.1 бар")

class SessionResponse(BaseModel):
    id: int = Field(..., example=42)
    started_at: str = Field(..., example="2025-04-05T12:34:56.789")
    ended_at: Optional[str] = None
    status: str = Field(..., example="running")

class SensorStatsResponse(BaseModel):
    count: int = Field(..., example=15)
    avg: Optional[float] = Field(None, example=98.7)
    min: Optional[float] = Field(None, example=45.2)
    max: Optional[float] = Field(None, example=178.9)

class EventResponse(BaseModel):
    id: int
    session_id: int
    timestamp: str
    event_type: str
    severity: str
    message: str

class SensorReadingResponse(BaseModel):
    id: int
    sensor_type: str
    timestamp: str
    value: float
    unit: Optional[str]

class ActuatorCommandResponse(BaseModel):
    id: int
    actuator_type: str
    timestamp: str
    command: float
    status: Optional[str]