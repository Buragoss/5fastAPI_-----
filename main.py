from fastapi import FastAPI, HTTPException, Query
from typing import Optional, List
from models import *
from database import db

app = FastAPI(
    title="Robot Telemetry API",
    description="Практическая работа 5",
    version="1.0"
)

@app.on_event("startup")
async def startup():
    db.connect()
    db.init_schema()

@app.on_event("shutdown")
async def shutdown():
    db.close()

@app.get("/health")
async def health(): 
    return {"status": "ok"}

# === СЕССИИ ===
@app.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(payload: SessionCreate):
    session_id = db.create_session(payload.variant_id)
    return db.get_session(session_id)

@app.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(limit: int = Query(100, ge=1, le=1000)):
    return db.list_sessions(limit)

@app.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int):
    session = db.get_session(session_id)
    if not session: 
        raise HTTPException(404, "Session not found")
    return session

@app.post("/sessions/{session_id}/end", response_model=SessionResponse)
async def end_session(session_id: int, payload: SessionEnd):
    session = db.get_session(session_id)
    if not session: 
        raise HTTPException(404, "Session not found")
    if session["status"] != "running":
        raise HTTPException(400, "Session already ended")
    db.end_session(session_id, payload.status)
    return db.get_session(session_id)


@app.post("/sessions/{session_id}/sensors", status_code=201)
async def log_sensor(session_id: int, payload: SensorReading):
    if not db.get_session(session_id): 
        raise HTTPException(404, "Session not found")
    db.log_sensor(session_id, payload.sensor_type, payload.value, payload.unit)
    return {"detail": "logged"}

@app.post("/sessions/{session_id}/actuators", status_code=201)
async def log_actuator(session_id: int, payload: ActuatorCommand):
    if not db.get_session(session_id): 
        raise HTTPException(404, "Session not found")
    db.log_command(session_id, payload.actuator_type, payload.command, payload.status)
    return {"detail": "logged"}

@app.post("/sessions/{session_id}/events", status_code=201)
async def log_event(session_id: int, payload: EventLog):
    if not db.get_session(session_id): 
        raise HTTPException(404, "Session not found")
    db.log_event(session_id, payload.event_type, payload.severity, payload.message)
    return {"detail": "logged"}

@app.get("/sessions/{session_id}/sensors/{sensor_type}/stats", response_model=SensorStatsResponse)
async def sensor_stats(session_id: int, sensor_type: str):
    if not db.get_session(session_id): 
        raise HTTPException(404, "Session not found")
    stats = db.sensor_stats(session_id, sensor_type)
    if not stats or stats["count"] == 0:
        raise HTTPException(404, f"No data for sensor {sensor_type}")
    return stats

@app.get("/sessions/{session_id}/events", response_model=List[EventResponse])
async def get_events(session_id: int, severity: Optional[str] = None):
    if not db.get_session(session_id): 
        raise HTTPException(404, "Session not found")
    return db.list_events(session_id, severity)

@app.get("/sessions/{session_id}/sensors", response_model=List[SensorReadingResponse])
async def list_sensors(session_id: int, sensor_type: Optional[str] = None):
    if not db.get_session(session_id): 
        raise HTTPException(404, "Session not found")
    return db.list_sensor_readings(session_id, sensor_type)

@app.get("/sessions/{session_id}/actuators", response_model=List[ActuatorCommandResponse])
async def list_actuators(session_id: int, actuator_type: Optional[str] = None):
    if not db.get_session(session_id): 
        raise HTTPException(404, "Session not found")
    return db.list_actuator_commands(session_id, actuator_type)