from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import logging
import uuid
import bcrypt
import jwt
import math
import random
from typing import List, Optional, Annotated
from datetime import datetime, timezone, timedelta, date
from collections import defaultdict

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

UPLOAD_DIR = ROOT_DIR / "uploads" / "athletes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMG_EXT = {"jpg", "jpeg", "png", "webp"}

app = FastAPI()
api = APIRouter(prefix="/api")

JWT_ALGO = "HS256"
JWT_SECRET = os.environ["JWT_SECRET"]


# ---------------------- Helpers ----------------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Não autenticado")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        if payload.get("type") != "access":
            raise HTTPException(401, "Tipo de token inválido")
        user = await db.users.find_one({"id": payload["sub"]})
        if not user:
            raise HTTPException(401, "Utilizador não encontrado")
        user.pop("_id", None)
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sessão expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=86400,
        path="/",
    )


# ---------------------- Models ----------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TeamIn(BaseModel):
    name: str
    escalao: str
    epoca: str


class AthleteIn(BaseModel):
    name: str
    position: Optional[str] = None
    jersey_number: Optional[int] = None
    birth_date: Optional[str] = None


class SessionIn(BaseModel):
    athlete_id: str
    date: str  # YYYY-MM-DD
    rpe: int = Field(ge=1, le=10)
    duration_min: int = Field(ge=1, le=300)
    sleep_quality: int = Field(ge=1, le=5)
    wellness: int = Field(ge=1, le=10, default=7)  # bem-estar corporal 1-10
    session_type: str = Field(default="training")  # training|match|gym|recovery
    notes: Optional[str] = None


class SessionUpdate(BaseModel):
    date: Optional[str] = None
    rpe: Optional[int] = Field(default=None, ge=1, le=10)
    duration_min: Optional[int] = Field(default=None, ge=1, le=300)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=5)
    wellness: Optional[int] = Field(default=None, ge=1, le=10)
    session_type: Optional[str] = None
    notes: Optional[str] = None


VALID_SESSION_TYPES = {"training", "match", "gym", "recovery"}


class InjuryIn(BaseModel):
    athlete_id: str
    type: str
    body_part: str
    start_date: str  # YYYY-MM-DD
    end_date: Optional[str] = None
    severity: str = Field(default="medium")  # low|medium|high
    notes: Optional[str] = None


class PlannedSessionIn(BaseModel):
    date: str  # YYYY-MM-DD
    planned_rpe: int = Field(ge=1, le=10)
    planned_duration: int = Field(ge=1, le=300)
    notes: Optional[str] = None
    athlete_ids: Optional[List[str]] = None  # None or [] means team-wide


# ---------------------- Auth Routes ----------------------
@api.post("/auth/register")
async def register(data: RegisterIn, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email já registado")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name,
        "role": "coach",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    token = create_access_token(user_id, email)
    set_auth_cookie(response, token)
    return {"id": user_id, "email": email, "name": data.name, "role": "coach", "token": token}


@api.post("/auth/login")
async def login(data: LoginIn, response: Response):
    email = data.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Credenciais inválidas")
    token = create_access_token(user["id"], email)
    set_auth_cookie(response, token)
    return {
        "id": user["id"],
        "email": email,
        "name": user.get("name"),
        "role": user.get("role", "coach"),
        "token": token,
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user


MAX_TEAMS_PER_USER = 5
TEAM_LOGO_DIR = ROOT_DIR / "uploads" / "teams"
TEAM_LOGO_DIR.mkdir(parents=True, exist_ok=True)


async def _get_active_team(user, required: bool = True):
    """Return the user's active team (by users.active_team_id), or first team as fallback.
    Auto-activates the first team if active_team_id is missing/invalid."""
    active_id = user.get("active_team_id")
    team = None
    if active_id:
        team = await db.teams.find_one({"id": active_id, "user_id": user["id"]})
    if not team:
        team = await db.teams.find_one({"user_id": user["id"]})
        if team:
            await db.users.update_one({"id": user["id"]}, {"$set": {"active_team_id": team["id"]}})
    if not team and required:
        raise HTTPException(400, "Insira dados da equipa primeiro")
    return team


# ---------------------- Team ----------------------
@api.get("/team")
async def get_team(user=Depends(get_current_user)):
    """Returns ACTIVE team (back-compat single-team API)."""
    team = await _get_active_team(user, required=False)
    if team:
        team.pop("_id", None)
    return team


@api.post("/team")
async def upsert_team(data: TeamIn, user=Depends(get_current_user)):
    """Upserts active team (back-compat). If no teams exist, creates the first."""
    active = await _get_active_team(user, required=False)
    if active:
        await db.teams.update_one(
            {"id": active["id"]},
            {"$set": {"name": data.name, "escalao": data.escalao, "epoca": data.epoca}},
        )
        team = await db.teams.find_one({"id": active["id"]}, {"_id": 0})
        return team
    team_id = str(uuid.uuid4())
    doc = {
        "id": team_id,
        "user_id": user["id"],
        "name": data.name,
        "escalao": data.escalao,
        "epoca": data.epoca,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.teams.insert_one(doc)
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_team_id": team_id}})
    doc.pop("_id", None)
    return doc


@api.get("/teams")
async def list_teams(user=Depends(get_current_user)):
    """List all teams for the current user, with active flag."""
    # ensure active_team_id is set if user has at least one team
    await _get_active_team(user, required=False)
    refreshed = await db.users.find_one({"id": user["id"]}, {"_id": 0})
    active_id = refreshed.get("active_team_id") if refreshed else None
    teams = await db.teams.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", 1).to_list(20)
    for t in teams:
        t["active"] = (t["id"] == active_id)
    return teams


@api.post("/teams")
async def create_team(data: TeamIn, user=Depends(get_current_user)):
    """Create a new team (max 5 per user). Newly-created team becomes active."""
    count = await db.teams.count_documents({"user_id": user["id"]})
    if count >= MAX_TEAMS_PER_USER:
        raise HTTPException(400, f"Limite de {MAX_TEAMS_PER_USER} equipas atingido")
    team_id = str(uuid.uuid4())
    doc = {
        "id": team_id,
        "user_id": user["id"],
        "name": data.name,
        "escalao": data.escalao,
        "epoca": data.epoca,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.teams.insert_one(doc)
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_team_id": team_id}})
    doc.pop("_id", None)
    doc["active"] = True
    return doc


@api.put("/teams/{team_id}")
async def update_team_by_id(team_id: str, data: TeamIn, user=Depends(get_current_user)):
    existing = await db.teams.find_one({"id": team_id, "user_id": user["id"]})
    if not existing:
        raise HTTPException(404, "Equipa não encontrada")
    await db.teams.update_one(
        {"id": team_id},
        {"$set": {"name": data.name, "escalao": data.escalao, "epoca": data.epoca}},
    )
    refreshed = await db.teams.find_one({"id": team_id}, {"_id": 0})
    return refreshed


@api.delete("/teams/{team_id}")
async def delete_team_by_id(team_id: str, user=Depends(get_current_user)):
    existing = await db.teams.find_one({"id": team_id, "user_id": user["id"]})
    if not existing:
        raise HTTPException(404, "Equipa não encontrada")
    # cascade delete
    async for a in db.athletes.find({"team_id": team_id}):
        if a.get("photo_path"):
            try:
                (UPLOAD_DIR / a["photo_path"]).unlink(missing_ok=True)
            except Exception:
                pass
    if existing.get("logo_path"):
        try:
            (TEAM_LOGO_DIR / existing["logo_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    await db.sessions.delete_many({"team_id": team_id})
    await db.athletes.delete_many({"team_id": team_id})
    await db.injuries.delete_many({"team_id": team_id})
    await db.planned_sessions.delete_many({"team_id": team_id})
    await db.teams.delete_one({"id": team_id})
    # if active was this team, switch to another (first available)
    if user.get("active_team_id") == team_id:
        other = await db.teams.find_one({"user_id": user["id"]})
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"active_team_id": other["id"] if other else None}},
        )
    return {"ok": True}


@api.post("/teams/{team_id}/activate")
async def activate_team(team_id: str, user=Depends(get_current_user)):
    existing = await db.teams.find_one({"id": team_id, "user_id": user["id"]})
    if not existing:
        raise HTTPException(404, "Equipa não encontrada")
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_team_id": team_id}})
    return {"ok": True, "active_team_id": team_id}


@api.post("/teams/{team_id}/logo")
async def upload_team_logo(team_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    team = await db.teams.find_one({"id": team_id, "user_id": user["id"]})
    if not team:
        raise HTTPException(404, "Equipa não encontrada")
    ext = (file.filename.rsplit(".", 1)[-1] or "").lower() if file.filename else ""
    if ext not in ALLOWED_IMG_EXT:
        raise HTTPException(400, "Formato inválido. Use JPG, PNG ou WebP")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Imagem demasiado grande (máx 5MB)")
    if team.get("logo_path"):
        try:
            (TEAM_LOGO_DIR / team["logo_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    filename = f"{team_id}_{uuid.uuid4().hex[:8]}.{ext}"
    (TEAM_LOGO_DIR / filename).write_bytes(data)
    await db.teams.update_one(
        {"id": team_id},
        {"$set": {"logo_path": filename, "logo_updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "logo_path": filename, "url": f"/api/teams/{team_id}/logo"}


@api.delete("/teams/{team_id}/logo")
async def remove_team_logo(team_id: str, user=Depends(get_current_user)):
    team = await db.teams.find_one({"id": team_id, "user_id": user["id"]})
    if not team:
        raise HTTPException(404, "Equipa não encontrada")
    if team.get("logo_path"):
        try:
            (TEAM_LOGO_DIR / team["logo_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    await db.teams.update_one({"id": team_id}, {"$set": {"logo_path": None}})
    return {"ok": True}


@api.get("/teams/{team_id}/logo")
async def get_team_logo(team_id: str):
    """Public logo endpoint so <img src> works directly."""
    team = await db.teams.find_one({"id": team_id})
    if not team or not team.get("logo_path"):
        raise HTTPException(404, "Sem logo")
    fp = TEAM_LOGO_DIR / team["logo_path"]
    if not fp.exists():
        raise HTTPException(404, "Ficheiro não encontrado")
    ext = team["logo_path"].rsplit(".", 1)[-1].lower()
    mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return FileResponse(fp, media_type=mt)


# ---------------------- Athletes ----------------------
async def _get_team_or_404(user):
    """Returns the user's ACTIVE team or raises 400."""
    return await _get_active_team(user, required=True)


@api.get("/athletes")
async def list_athletes(user=Depends(get_current_user)):
    team = await _get_active_team(user, required=False)
    if not team:
        return []
    athletes = await db.athletes.find({"team_id": team["id"]}, {"_id": 0}).to_list(500)
    return athletes


@api.post("/athletes")
async def create_athlete(data: AthleteIn, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    athlete_id = str(uuid.uuid4())
    doc = {
        "id": athlete_id,
        "team_id": team["id"],
        "name": data.name,
        "position": data.position,
        "jersey_number": data.jersey_number,
        "birth_date": data.birth_date,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.athletes.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/athletes/{athlete_id}")
async def delete_athlete(athlete_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    # remove photo file
    a = await db.athletes.find_one({"id": athlete_id, "team_id": team["id"]})
    if a and a.get("photo_path"):
        try:
            (UPLOAD_DIR / a["photo_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    await db.athletes.delete_one({"id": athlete_id, "team_id": team["id"]})
    await db.sessions.delete_many({"athlete_id": athlete_id})
    await db.injuries.delete_many({"athlete_id": athlete_id})
    return {"ok": True}


@api.post("/athletes/{athlete_id}/photo")
async def upload_photo(athlete_id: str, file: UploadFile = File(...), user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": athlete_id, "team_id": team["id"]})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    ext = (file.filename.rsplit(".", 1)[-1] or "").lower() if file.filename else ""
    if ext not in ALLOWED_IMG_EXT:
        raise HTTPException(400, "Formato inválido. Use JPG, PNG ou WebP")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Imagem demasiado grande (máx 5MB)")

    # remove old photo
    if athlete.get("photo_path"):
        try:
            (UPLOAD_DIR / athlete["photo_path"]).unlink(missing_ok=True)
        except Exception:
            pass

    filename = f"{athlete_id}_{uuid.uuid4().hex[:8]}.{ext}"
    (UPLOAD_DIR / filename).write_bytes(data)

    await db.athletes.update_one(
        {"id": athlete_id, "team_id": team["id"]},
        {"$set": {"photo_path": filename, "photo_updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "photo_path": filename, "url": f"/api/athletes/{athlete_id}/photo"}


@api.delete("/athletes/{athlete_id}/photo")
async def remove_photo(athlete_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": athlete_id, "team_id": team["id"]})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    if athlete.get("photo_path"):
        try:
            (UPLOAD_DIR / athlete["photo_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    await db.athletes.update_one(
        {"id": athlete_id, "team_id": team["id"]},
        {"$set": {"photo_path": None}},
    )
    return {"ok": True}


@api.get("/athletes/{athlete_id}/photo")
async def get_photo(athlete_id: str):
    """Public photo endpoint (no auth) so <img src> works directly."""
    athlete = await db.athletes.find_one({"id": athlete_id})
    if not athlete or not athlete.get("photo_path"):
        raise HTTPException(404, "Sem foto")
    fp = UPLOAD_DIR / athlete["photo_path"]
    if not fp.exists():
        raise HTTPException(404, "Ficheiro não encontrado")
    ext = athlete["photo_path"].rsplit(".", 1)[-1].lower()
    mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    return FileResponse(fp, media_type=mt)


# ---------------------- Sessions ----------------------
@api.post("/sessions")
async def create_session(data: SessionIn, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": data.athlete_id, "team_id": team["id"]})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    if data.session_type not in VALID_SESSION_TYPES:
        raise HTTPException(400, "Tipo de sessão inválido")
    session_id = str(uuid.uuid4())
    load = data.rpe * data.duration_min
    doc = {
        "id": session_id,
        "athlete_id": data.athlete_id,
        "team_id": team["id"],
        "date": data.date,
        "rpe": data.rpe,
        "duration_min": data.duration_min,
        "sleep_quality": data.sleep_quality,
        "wellness": data.wellness,
        "session_type": data.session_type,
        "load": load,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.put("/sessions/{session_id}")
async def update_session(session_id: str, data: SessionUpdate, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    existing = await db.sessions.find_one({"id": session_id, "team_id": team["id"]})
    if not existing:
        raise HTTPException(404, "Sessão não encontrada")
    updates = {}
    if data.date is not None:
        updates["date"] = data.date
    if data.rpe is not None:
        updates["rpe"] = data.rpe
    if data.duration_min is not None:
        updates["duration_min"] = data.duration_min
    if data.sleep_quality is not None:
        updates["sleep_quality"] = data.sleep_quality
    if data.wellness is not None:
        updates["wellness"] = data.wellness
    if data.session_type is not None:
        if data.session_type not in VALID_SESSION_TYPES:
            raise HTTPException(400, "Tipo de sessão inválido")
        updates["session_type"] = data.session_type
    if data.notes is not None:
        updates["notes"] = data.notes
    # recompute load if rpe or duration changed
    new_rpe = updates.get("rpe", existing["rpe"])
    new_dur = updates.get("duration_min", existing["duration_min"])
    updates["load"] = new_rpe * new_dur
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.sessions.update_one({"id": session_id}, {"$set": updates})
    refreshed = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    return refreshed


@api.get("/sessions")
async def list_sessions(athlete_id: Optional[str] = None, user=Depends(get_current_user)):
    team = await _get_active_team(user, required=False)
    if not team:
        return []
    q = {"team_id": team["id"]}
    if athlete_id:
        q["athlete_id"] = athlete_id
    sessions = await db.sessions.find(q, {"_id": 0}).sort("date", -1).to_list(5000)
    return sessions


@api.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    await db.sessions.delete_one({"id": session_id, "team_id": team["id"]})
    return {"ok": True}


# ---------------------- Analytics ----------------------
def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def compute_metrics_for_athlete(sessions: list, ref_date: Optional[date] = None) -> dict:
    """Compute ACWR, acute, chronic, monotony, strain, risk for one athlete."""
    if ref_date is None:
        ref_date = date.today()

    # group loads by day
    by_day = defaultdict(float)
    sleep_by_day = {}
    dates_set = []
    for s in sessions:
        d = _parse_date(s["date"])
        by_day[d] += s["load"]
        sleep_by_day[d] = s["sleep_quality"]
        dates_set.append(d)

    if not dates_set:
        return {
            "acute": 0,
            "chronic": 0,
            "acwr": 0,
            "monotony": 0,
            "strain": 0,
            "risk": "no_data",
            "days_since_first": 0,
            "sufficient_data": False,
            "total_sessions": 0,
            "avg_load": 0,
            "avg_sleep": 0,
            "avg_wellness": 0,
            "wellness_zone": "no_data",
        }

    first_date = min(dates_set)
    days_since_first = (ref_date - first_date).days

    # acute: last 7 days
    acute = sum(by_day.get(ref_date - timedelta(days=i), 0) for i in range(7))
    # chronic: avg of weekly loads over last 28 days (4 weeks)
    weekly_loads = []
    for w in range(4):
        s = sum(by_day.get(ref_date - timedelta(days=i), 0) for i in range(w * 7, (w + 1) * 7))
        weekly_loads.append(s)
    chronic = sum(weekly_loads) / 4 if weekly_loads else 0

    acwr = round(acute / chronic, 2) if chronic > 0 else 0

    # monotony & strain (last 7 days)
    week_loads = [by_day.get(ref_date - timedelta(days=i), 0) for i in range(7)]
    mean_l = sum(week_loads) / 7
    var_l = sum((x - mean_l) ** 2 for x in week_loads) / 7
    std_l = math.sqrt(var_l)
    monotony = round(mean_l / std_l, 2) if std_l > 0 else 0
    strain = round(sum(week_loads) * monotony, 2) if monotony else 0

    sufficient = days_since_first >= 28

    # ---- Classify each metric by user-defined thresholds ----
    # Monotonia
    if monotony == 0:
        mono_zone = "no_data"
    elif monotony < 1.0:
        mono_zone = "high_variation"      # boa
    elif monotony <= 1.5:
        mono_zone = "ideal"
    elif monotony <= 2.0:
        mono_zone = "moderate_high"
    else:
        mono_zone = "critical"

    # Strain
    if strain == 0:
        strain_zone = "no_data"
    elif strain < 1500:
        strain_zone = "low"
    elif strain <= 3000:
        strain_zone = "moderate"
    elif strain <= 6000:
        strain_zone = "elevated"
    else:
        strain_zone = "extreme"

    # ACWR
    if acwr == 0:
        acwr_zone = "no_data"
    elif acwr < 0.8:
        acwr_zone = "detraining"
    elif acwr <= 1.3:
        acwr_zone = "sweet_spot"
    elif acwr < 1.5:
        acwr_zone = "alert"
    else:
        acwr_zone = "high_risk"

    # ---- Wellness (Bem-Estar Corporal) over last 7 days ----
    recent_sessions = [
        s for s in sessions
        if _parse_date(s["date"]) >= ref_date - timedelta(days=6)
        and "wellness" in s and s.get("wellness") is not None
    ]
    if recent_sessions:
        avg_wellness_7d = round(sum(s["wellness"] for s in recent_sessions) / len(recent_sessions), 1)
    else:
        avg_wellness_7d = 0

    if avg_wellness_7d == 0:
        wellness_zone = "no_data"
    elif avg_wellness_7d <= 2:
        wellness_zone = "depleted"
    elif avg_wellness_7d <= 4:
        wellness_zone = "fatigued"
    elif avg_wellness_7d <= 6:
        wellness_zone = "moderate"
    elif avg_wellness_7d <= 8:
        wellness_zone = "good"
    else:
        wellness_zone = "excellent"

    # ---- Risk classification (combined ACWR + Monotonia + Strain + Bem-Estar) ----
    risk_reasons = []
    if not sufficient:
        risk = "insufficient"
    elif acwr == 0:
        risk = "low"
        risk_reasons.append("Sem treinos recentes")
    else:
        base = "safe"

        # ACWR contribution
        if acwr_zone == "detraining":
            base = "warning"
            risk_reasons.append("Sub-treinamento — ACWR abaixo de 0.8 (zona de destreinamento)")
        elif acwr_zone == "sweet_spot":
            pass
        elif acwr_zone == "alert":
            if base == "safe":
                base = "warning"
            risk_reasons.append("Carga elevada — ACWR entre 1.3 e 1.5 (zona de alerta)")
        elif acwr_zone == "high_risk":
            base = "danger"
            risk_reasons.append("Risco de lesão — ACWR ≥ 1.5 (zona de alto risco)")

        # Monotonia contribution
        if mono_zone == "critical":
            risk_reasons.append("Monotonia crítica (>2.0) — treinos sem variação, risco de overtraining")
            base = "danger"
        elif mono_zone == "moderate_high":
            risk_reasons.append("Monotonia moderada-alta (1.5–2.0) — pouca variação")
            if base == "safe":
                base = "warning"

        # Strain contribution
        if strain_zone == "extreme":
            risk_reasons.append("Strain extremo (>6000) — risco de lesão, queda de desempenho")
            base = "danger"
        elif strain_zone == "elevated":
            risk_reasons.append("Strain elevado (3000–6000) — monitorizar de perto")
            if base == "safe":
                base = "warning"

        # Bem-Estar Corporal contribution (last 7 days)
        if wellness_zone == "depleted":
            risk_reasons.append("Bem-estar corporal crítico (1–2) — esgotamento profundo / dor / doença")
            base = "danger"
        elif wellness_zone == "fatigued":
            risk_reasons.append("Bem-estar corporal baixo (3–4) — cansaço extremo / letargia")
            if base == "safe":
                base = "warning"
            elif base == "warning":
                base = "danger"
        elif wellness_zone == "moderate":
            risk_reasons.append("Bem-estar moderado (5–6) — alguma tensão")

        risk = base

    risk_label_map = {
        "safe": "Ótimo",
        "warning": "Atenção",
        "danger": "Risco Elevado",
        "low": "Baixa Carga",
        "insufficient": "Dados Insuficientes",
        "no_data": "Sem Dados",
    }
    if not risk_reasons:
        risk_description = "Carga, monotonia e strain em zonas seguras" if risk == "safe" else risk_label_map.get(risk, "")
    else:
        risk_description = " · ".join(risk_reasons)

    avg_load = round(sum(s["load"] for s in sessions) / len(sessions), 1)
    avg_sleep = round(sum(s["sleep_quality"] for s in sessions) / len(sessions), 1)
    wellness_vals = [s.get("wellness") for s in sessions if s.get("wellness") is not None]
    avg_wellness = round(sum(wellness_vals) / len(wellness_vals), 1) if wellness_vals else 0

    return {
        "acute": round(acute, 1),
        "chronic": round(chronic, 1),
        "acwr": acwr,
        "acwr_zone": acwr_zone,
        "monotony": monotony,
        "monotony_zone": mono_zone,
        "strain": strain,
        "strain_zone": strain_zone,
        "wellness_7d": avg_wellness_7d,
        "wellness_zone": wellness_zone,
        "avg_wellness": avg_wellness,
        "risk": risk,
        "risk_label": risk_label_map.get(risk, ""),
        "risk_description": risk_description,
        "risk_reasons": risk_reasons,
        "days_since_first": days_since_first,
        "sufficient_data": sufficient,
        "total_sessions": len(sessions),
        "avg_load": avg_load,
        "avg_sleep": avg_sleep,
        "first_date": first_date.isoformat(),
    }


@api.get("/analytics/athlete/{athlete_id}")
async def analytics_athlete(athlete_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": athlete_id, "team_id": team["id"]}, {"_id": 0})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    sessions = await db.sessions.find({"athlete_id": athlete_id}, {"_id": 0}).to_list(5000)
    metrics = compute_metrics_for_athlete(sessions)

    # daily time series for ACWR chart (last 60 days)
    ref = date.today()
    by_day = defaultdict(float)
    for s in sessions:
        by_day[_parse_date(s["date"])] += s["load"]

    series = []
    for i in range(59, -1, -1):
        d = ref - timedelta(days=i)
        acute = sum(by_day.get(d - timedelta(days=j), 0) for j in range(7))
        weekly = []
        for w in range(4):
            ws = sum(by_day.get(d - timedelta(days=j), 0) for j in range(w * 7, (w + 1) * 7))
            weekly.append(ws)
        chronic = sum(weekly) / 4
        acwr = round(acute / chronic, 2) if chronic > 0 else 0
        series.append({
            "date": d.isoformat(),
            "load": round(by_day.get(d, 0), 1),
            "acute": round(acute, 1),
            "chronic": round(chronic, 1),
            "acwr": acwr,
        })

    return {"athlete": athlete, "metrics": metrics, "series": series, "sessions": sessions}


@api.get("/analytics/team")
async def analytics_team(user=Depends(get_current_user)):
    team = await _get_active_team(user, required=False)
    if team:
        team = {k: v for k, v in team.items() if k != "_id"}
    if not team:
        return {"team": None, "athletes": [], "summary": {}}
    athletes = await db.athletes.find({"team_id": team["id"]}, {"_id": 0}).to_list(500)
    out_athletes = []
    total_acute = 0
    total_chronic = 0
    total_monotony = 0
    total_sleep = 0
    total_wellness = 0
    sleep_count = 0
    wellness_count = 0
    counted = 0
    risk_counts = {"safe": 0, "warning": 0, "danger": 0, "insufficient": 0, "low": 0, "no_data": 0}
    for a in athletes:
        sessions = await db.sessions.find({"athlete_id": a["id"]}, {"_id": 0}).to_list(5000)
        m = compute_metrics_for_athlete(sessions)
        out_athletes.append({**a, "metrics": m})
        risk_counts[m["risk"]] = risk_counts.get(m["risk"], 0) + 1
        if m["sufficient_data"]:
            total_acute += m["acute"]
            total_chronic += m["chronic"]
            counted += 1
        if m.get("monotony"):
            total_monotony += m["monotony"]
        if m.get("avg_sleep"):
            total_sleep += m["avg_sleep"]
            sleep_count += 1
        if m.get("wellness_7d"):
            total_wellness += m["wellness_7d"]
            wellness_count += 1

    monotony_count = sum(1 for a in out_athletes if a["metrics"].get("monotony"))
    avg_monotony = round(total_monotony / monotony_count, 2) if monotony_count else 0
    if avg_monotony == 0:
        mono_zone = "no_data"
    elif avg_monotony < 1.0:
        mono_zone = "high_variation"
    elif avg_monotony <= 1.5:
        mono_zone = "ideal"
    elif avg_monotony <= 2.0:
        mono_zone = "moderate_high"
    else:
        mono_zone = "critical"

    summary = {
        "athletes_count": len(athletes),
        "avg_acute": round(total_acute / counted, 1) if counted else 0,
        "avg_chronic": round(total_chronic / counted, 1) if counted else 0,
        "avg_sleep": round(total_sleep / sleep_count, 2) if sleep_count else 0,
        "avg_wellness": round(total_wellness / wellness_count, 2) if wellness_count else 0,
        "avg_monotony": avg_monotony,
        "avg_monotony_zone": mono_zone,
        "risk_counts": risk_counts,
        "athletes_with_sufficient_data": counted,
    }
    return {"team": team, "athletes": out_athletes, "summary": summary}


# ---------------------- Monthly Summary ----------------------
def _week_key(d: date) -> str:
    """Return ISO week key as YYYY-Www."""
    iso = d.isocalendar()
    return f"{iso[0]:04d}-W{iso[1]:02d}"


def _week_start(year: int, week: int) -> date:
    """Return Monday date of given ISO year + week."""
    return date.fromisocalendar(year, week, 1)


def _format_week_label(key: str) -> str:
    y, w = key.split("-W")
    return f"S{int(w):02d}/{y[-2:]}"


def _last_n_weeks(today_d: date, n: int):
    """Return list of last n ISO week keys ending with current week."""
    keys = []
    iso = today_d.isocalendar()
    y, w = iso[0], iso[1]
    for _ in range(n):
        keys.append(f"{y:04d}-W{w:02d}")
        # go back one week
        first_of_week = date.fromisocalendar(y, w, 1)
        prev = first_of_week - timedelta(days=1)
        iso2 = prev.isocalendar()
        y, w = iso2[0], iso2[1]
    keys.reverse()
    return keys


@api.get("/analytics/weekly/{athlete_id}")
async def weekly_summary(athlete_id: str, weeks: int = 8, user=Depends(get_current_user)):
    """Weekly average load + sleep + wellness + evolution vs previous week, last N weeks."""
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": athlete_id, "team_id": team["id"]}, {"_id": 0})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    sessions = await db.sessions.find({"athlete_id": athlete_id}, {"_id": 0}).to_list(5000)

    by_week = defaultdict(list)
    for s in sessions:
        d = _parse_date(s["date"])
        by_week[_week_key(d)].append(s)

    today_d = date.today()
    keys = _last_n_weeks(today_d, weeks)

    weeks_out = []
    prev_avg = None
    for k in keys:
        ws = by_week.get(k, [])
        if ws:
            total_load = sum(s["load"] for s in ws)
            avg_load = round(total_load / len(ws), 1)
            avg_sleep = round(sum(s["sleep_quality"] for s in ws) / len(ws), 2)
            wellness_vals = [s.get("wellness") for s in ws if s.get("wellness") is not None]
            avg_wellness = round(sum(wellness_vals) / len(wellness_vals), 1) if wellness_vals else 0
            sessions_count = len(ws)
        else:
            total_load = 0
            avg_load = 0
            avg_sleep = 0
            avg_wellness = 0
            sessions_count = 0
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load > 0:
            prev_avg = avg_load
        # parse week start date
        y, w = k.split("-W")
        start_d = _week_start(int(y), int(w))
        weeks_out.append({
            "week": k,
            "label": _format_week_label(k),
            "start_date": start_d.isoformat(),
            "end_date": (start_d + timedelta(days=6)).isoformat(),
            "sessions": sessions_count,
            "total_load": round(total_load, 1),
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "avg_wellness": avg_wellness,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    valid = [m for m in weeks_out if m["avg_load"] > 0]
    if len(valid) >= 2:
        first_v = valid[0]["avg_load"]
        last_v = valid[-1]["avg_load"]
        evolution = "subiu" if last_v > first_v else "desceu" if last_v < first_v else "estável"
        evolution_pct = round((last_v - first_v) / first_v * 100, 1) if first_v > 0 else 0
    else:
        evolution = "indeterminado"
        evolution_pct = 0

    return {
        "athlete": athlete,
        "weeks": weeks_out,
        "evolution": evolution,
        "evolution_pct": evolution_pct,
    }


@api.get("/analytics/monthly/{athlete_id}")
async def monthly_summary(athlete_id: str, months: int = 6, user=Depends(get_current_user)):
    """[Legacy] Monthly summary kept for backward compatibility."""
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": athlete_id, "team_id": team["id"]}, {"_id": 0})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    sessions = await db.sessions.find({"athlete_id": athlete_id}, {"_id": 0}).to_list(5000)

    # group by YYYY-MM
    by_month = defaultdict(list)
    for s in sessions:
        key = s["date"][:7]
        by_month[key].append(s)

    # determine last N months from today
    today = date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys.reverse()

    months_out = []
    prev_avg = None
    for k in keys:
        ms = by_month.get(k, [])
        if ms:
            total_load = sum(s["load"] for s in ms)
            avg_load = round(total_load / len(ms), 1)
            avg_sleep = round(sum(s["sleep_quality"] for s in ms) / len(ms), 2)
            sessions_count = len(ms)
        else:
            total_load = 0
            avg_load = 0
            avg_sleep = 0
            sessions_count = 0
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load > 0:
            prev_avg = avg_load
        months_out.append({
            "month": k,
            "sessions": sessions_count,
            "total_load": round(total_load, 1),
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    # overall evolution
    valid = [m for m in months_out if m["avg_load"] > 0]
    if len(valid) >= 2:
        first = valid[0]["avg_load"]
        last = valid[-1]["avg_load"]
        evolution = "subiu" if last > first else "desceu" if last < first else "estável"
        evolution_pct = round((last - first) / first * 100, 1) if first > 0 else 0
    else:
        evolution = "indeterminado"
        evolution_pct = 0

    return {
        "athlete": athlete,
        "months": months_out,
        "evolution": evolution,
        "evolution_pct": evolution_pct,
    }


# ---------------------- Compare 2 Athletes ----------------------
@api.get("/analytics/compare")
async def compare_athletes(a1: str, a2: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    out = []
    for aid in (a1, a2):
        athlete = await db.athletes.find_one({"id": aid, "team_id": team["id"]}, {"_id": 0})
        if not athlete:
            raise HTTPException(404, f"Atleta {aid} não encontrado")
        sessions = await db.sessions.find({"athlete_id": aid}, {"_id": 0}).to_list(5000)
        metrics = compute_metrics_for_athlete(sessions)

        ref = date.today()
        by_day = defaultdict(float)
        for s in sessions:
            by_day[_parse_date(s["date"])] += s["load"]

        series = []
        for i in range(59, -1, -1):
            d = ref - timedelta(days=i)
            acute = sum(by_day.get(d - timedelta(days=j), 0) for j in range(7))
            weekly = []
            for w in range(4):
                ws = sum(by_day.get(d - timedelta(days=j), 0) for j in range(w * 7, (w + 1) * 7))
                weekly.append(ws)
            chronic = sum(weekly) / 4
            acwr = round(acute / chronic, 2) if chronic > 0 else 0
            series.append({"date": d.isoformat(), "acute": round(acute, 1), "chronic": round(chronic, 1), "acwr": acwr})

        out.append({"athlete": athlete, "metrics": metrics, "series": series})

    # merge series by date for overlay chart
    merged = []
    s1, s2 = out[0]["series"], out[1]["series"]
    for i in range(len(s1)):
        merged.append({
            "date": s1[i]["date"],
            "a1_acwr": s1[i]["acwr"],
            "a2_acwr": s2[i]["acwr"],
            "a1_acute": s1[i]["acute"],
            "a2_acute": s2[i]["acute"],
        })

    return {"a1": out[0], "a2": out[1], "merged_series": merged}


# ---------------------- Injuries ----------------------
@api.get("/injuries")
async def list_injuries(athlete_id: Optional[str] = None, user=Depends(get_current_user)):
    team = await _get_active_team(user, required=False)
    if not team:
        return []
    q = {"team_id": team["id"]}
    if athlete_id:
        q["athlete_id"] = athlete_id
    items = await db.injuries.find(q, {"_id": 0}).sort("start_date", -1).to_list(500)
    return items


@api.post("/injuries")
async def create_injury(data: InjuryIn, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": data.athlete_id, "team_id": team["id"]})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    if data.severity not in ("low", "medium", "high"):
        raise HTTPException(400, "Severidade inválida")
    doc = {
        "id": str(uuid.uuid4()),
        "athlete_id": data.athlete_id,
        "team_id": team["id"],
        "type": data.type,
        "body_part": data.body_part,
        "start_date": data.start_date,
        "end_date": data.end_date,
        "severity": data.severity,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.injuries.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/injuries/{injury_id}")
async def delete_injury(injury_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    await db.injuries.delete_one({"id": injury_id, "team_id": team["id"]})
    return {"ok": True}


# ---------------------- Planned Sessions & Calendar ----------------------
@api.get("/planned-sessions")
async def list_planned(
    start: Optional[str] = None,
    end: Optional[str] = None,
    user=Depends(get_current_user),
):
    team = await _get_active_team(user, required=False)
    if not team:
        return []
    q = {"team_id": team["id"]}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    items = await db.planned_sessions.find(q, {"_id": 0}).sort("date", 1).to_list(1000)
    return items


@api.post("/planned-sessions")
async def create_planned(data: PlannedSessionIn, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    doc = {
        "id": str(uuid.uuid4()),
        "team_id": team["id"],
        "date": data.date,
        "planned_rpe": data.planned_rpe,
        "planned_duration": data.planned_duration,
        "planned_load": data.planned_rpe * data.planned_duration,
        "notes": data.notes,
        "athlete_ids": data.athlete_ids or [],  # empty list = team-wide
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.planned_sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.delete("/planned-sessions/{planned_id}")
async def delete_planned(planned_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    await db.planned_sessions.delete_one({"id": planned_id, "team_id": team["id"]})
    return {"ok": True}


@api.get("/calendar")
async def calendar_view(start: str, days: int = 28, user=Depends(get_current_user)):
    """Day-by-day aggregate of recorded sessions and planned sessions for the team."""
    team = await _get_active_team(user, required=False)
    if team:
        team = {k: v for k, v in team.items() if k != "_id"}
    if not team:
        return {"team": None, "days": []}
    start_d = _parse_date(start)
    end_d = start_d + timedelta(days=days - 1)
    end_iso = end_d.isoformat()
    sessions = await db.sessions.find(
        {"team_id": team["id"], "date": {"$gte": start, "$lte": end_iso}}, {"_id": 0}
    ).to_list(5000)
    planned = await db.planned_sessions.find(
        {"team_id": team["id"], "date": {"$gte": start, "$lte": end_iso}}, {"_id": 0}
    ).to_list(1000)
    athletes = await db.athletes.find({"team_id": team["id"]}, {"_id": 0}).to_list(500)
    a_map = {a["id"]: a for a in athletes}

    by_day_rec = defaultdict(list)
    for s in sessions:
        by_day_rec[s["date"]].append(s)
    by_day_plan = defaultdict(list)
    for p in planned:
        by_day_plan[p["date"]].append(p)

    out_days = []
    for i in range(days):
        d = (start_d + timedelta(days=i)).isoformat()
        rec = by_day_rec.get(d, [])
        plan = by_day_plan.get(d, [])
        total_load = sum(s["load"] for s in rec)
        athletes_trained = []
        for s in rec:
            a = a_map.get(s["athlete_id"], {})
            athletes_trained.append({
                "athlete_id": s["athlete_id"],
                "name": a.get("name", "—"),
                "jersey_number": a.get("jersey_number"),
                "rpe": s["rpe"],
                "duration_min": s["duration_min"],
                "load": s["load"],
                "session_type": s.get("session_type", "training"),
                "session_id": s["id"],
            })
        # session type counts for day badge display
        type_counts = defaultdict(int)
        for s in rec:
            type_counts[s.get("session_type", "training")] += 1
        out_days.append({
            "date": d,
            "weekday": (start_d + timedelta(days=i)).weekday(),
            "total_load": round(total_load, 1),
            "athletes_count": len(rec),
            "athletes": athletes_trained,
            "session_types": dict(type_counts),
            "planned": plan,
        })

    return {
        "team": team,
        "start": start,
        "end": end_iso,
        "days": out_days,
        "athletes": athletes,
    }


# ---------------------- Team-wide analytics ----------------------
def _team_metrics_from_daily(by_day: dict, ref_date: Optional[date] = None) -> dict:
    """Compute team-wide ACWR/monotony/strain from a {date: total_load} mapping."""
    if ref_date is None:
        ref_date = date.today()
    if not by_day:
        return {
            "acute": 0, "chronic": 0, "acwr": 0, "monotony": 0, "strain": 0,
            "sufficient_data": False, "days_since_first": 0,
            "acwr_zone": "no_data", "monotony_zone": "no_data", "strain_zone": "no_data",
        }
    first_date = min(by_day.keys())
    days_since_first = (ref_date - first_date).days
    acute = sum(by_day.get(ref_date - timedelta(days=i), 0) for i in range(7))
    weekly_loads = [
        sum(by_day.get(ref_date - timedelta(days=i), 0) for i in range(w * 7, (w + 1) * 7))
        for w in range(4)
    ]
    chronic = sum(weekly_loads) / 4 if weekly_loads else 0
    acwr = round(acute / chronic, 2) if chronic > 0 else 0
    week_loads = [by_day.get(ref_date - timedelta(days=i), 0) for i in range(7)]
    mean_l = sum(week_loads) / 7
    var_l = sum((x - mean_l) ** 2 for x in week_loads) / 7
    std_l = math.sqrt(var_l)
    monotony = round(mean_l / std_l, 2) if std_l > 0 else 0
    strain = round(sum(week_loads) * monotony, 2) if monotony else 0

    # zones
    if acwr == 0: acwr_zone = "no_data"
    elif acwr < 0.8: acwr_zone = "detraining"
    elif acwr <= 1.3: acwr_zone = "sweet_spot"
    elif acwr < 1.5: acwr_zone = "alert"
    else: acwr_zone = "high_risk"

    if monotony == 0: mono_zone = "no_data"
    elif monotony < 1.0: mono_zone = "high_variation"
    elif monotony <= 1.5: mono_zone = "ideal"
    elif monotony <= 2.0: mono_zone = "moderate_high"
    else: mono_zone = "critical"

    if strain == 0: strain_zone = "no_data"
    elif strain < 1500: strain_zone = "low"
    elif strain <= 3000: strain_zone = "moderate"
    elif strain <= 6000: strain_zone = "elevated"
    else: strain_zone = "extreme"

    return {
        "acute": round(acute, 1),
        "chronic": round(chronic, 1),
        "acwr": acwr,
        "monotony": monotony,
        "strain": strain,
        "sufficient_data": days_since_first >= 28,
        "days_since_first": days_since_first,
        "acwr_zone": acwr_zone,
        "monotony_zone": mono_zone,
        "strain_zone": strain_zone,
    }


@api.get("/analytics/team-detailed")
async def team_detailed(user=Depends(get_current_user)):
    """Team-wide ACWR series & metrics computed from average per-athlete daily load
    (so the magnitude is comparable to an individual athlete)."""
    team = await _get_active_team(user, required=False)
    if team:
        team = {k: v for k, v in team.items() if k != "_id"}
    if not team:
        return {"team": None, "metrics": None, "series": []}
    athletes = await db.athletes.find({"team_id": team["id"]}, {"_id": 0}).to_list(500)
    if not athletes:
        return {"team": team, "metrics": None, "series": []}
    sessions = await db.sessions.find({"team_id": team["id"]}, {"_id": 0}).to_list(20000)

    n_athletes = len(athletes)
    by_day = defaultdict(float)
    for s in sessions:
        by_day[_parse_date(s["date"])] += s["load"]
    # average per athlete (treat team as a "super athlete" with avg load)
    by_day_avg = {d: v / n_athletes for d, v in by_day.items()}

    metrics = _team_metrics_from_daily(by_day_avg)

    ref = date.today()
    series = []
    for i in range(59, -1, -1):
        d = ref - timedelta(days=i)
        acute = sum(by_day_avg.get(d - timedelta(days=j), 0) for j in range(7))
        weekly = [
            sum(by_day_avg.get(d - timedelta(days=j), 0) for j in range(w * 7, (w + 1) * 7))
            for w in range(4)
        ]
        chronic = sum(weekly) / 4
        acwr = round(acute / chronic, 2) if chronic > 0 else 0
        series.append({
            "date": d.isoformat(),
            "load": round(by_day_avg.get(d, 0), 1),
            "acute": round(acute, 1),
            "chronic": round(chronic, 1),
            "acwr": acwr,
        })

    return {"team": team, "metrics": metrics, "series": series, "n_athletes": n_athletes}


@api.get("/analytics/weekly/team/overview")
async def weekly_team_overview(weeks: int = 8, user=Depends(get_current_user)):
    """Team-wide weekly aggregates."""
    team = await _get_active_team(user, required=False)
    if team:
        team = {k: v for k, v in team.items() if k != "_id"}
    if not team:
        raise HTTPException(400, "Insira dados da equipa primeiro")
    athletes_count = await db.athletes.count_documents({"team_id": team["id"]})
    sessions = await db.sessions.find({"team_id": team["id"]}, {"_id": 0}).to_list(20000)

    by_week = defaultdict(list)
    for s in sessions:
        d = _parse_date(s["date"])
        by_week[_week_key(d)].append(s)

    today_d = date.today()
    keys = _last_n_weeks(today_d, weeks)

    weeks_out = []
    prev_avg = None
    for k in keys:
        ws = by_week.get(k, [])
        if ws:
            total_load = sum(s["load"] for s in ws)
            avg_load = round(total_load / len(ws), 1)
            avg_sleep = round(sum(s["sleep_quality"] for s in ws) / len(ws), 2)
            wellness_vals = [s.get("wellness") for s in ws if s.get("wellness") is not None]
            avg_wellness = round(sum(wellness_vals) / len(wellness_vals), 1) if wellness_vals else 0
            sessions_count = len(ws)
        else:
            total_load = 0
            avg_load = 0
            avg_sleep = 0
            avg_wellness = 0
            sessions_count = 0
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load > 0:
            prev_avg = avg_load
        y, w = k.split("-W")
        start_d = _week_start(int(y), int(w))
        weeks_out.append({
            "week": k,
            "label": _format_week_label(k),
            "start_date": start_d.isoformat(),
            "end_date": (start_d + timedelta(days=6)).isoformat(),
            "sessions": sessions_count,
            "total_load": round(total_load, 1),
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "avg_wellness": avg_wellness,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    valid = [m for m in weeks_out if m["avg_load"] > 0]
    if len(valid) >= 2:
        first_v = valid[0]["avg_load"]
        last_v = valid[-1]["avg_load"]
        evolution = "subiu" if last_v > first_v else "desceu" if last_v < first_v else "estável"
        evolution_pct = round((last_v - first_v) / first_v * 100, 1) if first_v > 0 else 0
    else:
        evolution = "indeterminado"
        evolution_pct = 0

    return {
        "team": team,
        "athletes_count": athletes_count,
        "weeks": weeks_out,
        "evolution": evolution,
        "evolution_pct": evolution_pct,
    }


@api.get("/analytics/monthly/team/overview")
async def monthly_team_overview(months: int = 6, user=Depends(get_current_user)):
    """Team-wide monthly aggregates."""
    team = await _get_active_team(user, required=False)
    if team:
        team = {k: v for k, v in team.items() if k != "_id"}
    if not team:
        raise HTTPException(400, "Insira dados da equipa primeiro")
    athletes_count = await db.athletes.count_documents({"team_id": team["id"]})
    sessions = await db.sessions.find({"team_id": team["id"]}, {"_id": 0}).to_list(20000)

    by_month = defaultdict(list)
    for s in sessions:
        by_month[s["date"][:7]].append(s)

    today = date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    keys.reverse()

    months_out = []
    prev_avg = None
    for k in keys:
        ms = by_month.get(k, [])
        if ms:
            total_load = sum(s["load"] for s in ms)
            avg_load = round(total_load / len(ms), 1)
            avg_sleep = round(sum(s["sleep_quality"] for s in ms) / len(ms), 2)
            sessions_count = len(ms)
        else:
            total_load = 0
            avg_load = 0
            avg_sleep = 0
            sessions_count = 0
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load > 0:
            prev_avg = avg_load
        months_out.append({
            "month": k,
            "sessions": sessions_count,
            "total_load": round(total_load, 1),
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    valid = [m for m in months_out if m["avg_load"] > 0]
    if len(valid) >= 2:
        first_v = valid[0]["avg_load"]
        last_v = valid[-1]["avg_load"]
        evolution = "subiu" if last_v > first_v else "desceu" if last_v < first_v else "estável"
        evolution_pct = round((last_v - first_v) / first_v * 100, 1) if first_v > 0 else 0
    else:
        evolution = "indeterminado"
        evolution_pct = 0

    return {
        "team": team,
        "athletes_count": athletes_count,
        "months": months_out,
        "evolution": evolution,
        "evolution_pct": evolution_pct,
    }


# ---------------------- Demo Data Seeding ----------------------
@api.post("/seed/demo")
async def seed_demo(user=Depends(get_current_user)):
    """Populate demo team, athletes & 45 days of sessions for current user."""
    # delete existing — wipes ACTIVE team data
    team = await _get_active_team(user, required=False)
    if team:
        await db.sessions.delete_many({"team_id": team["id"]})
        await db.athletes.delete_many({"team_id": team["id"]})
        await db.injuries.delete_many({"team_id": team["id"]})
        await db.planned_sessions.delete_many({"team_id": team["id"]})
        await db.teams.delete_one({"id": team["id"]})

    team_id = str(uuid.uuid4())
    await db.teams.insert_one({
        "id": team_id,
        "user_id": user["id"],
        "name": "Sporting Futsal Lisboa",
        "escalao": "Sénior",
        "epoca": "2025/2026",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Make the freshly-seeded team the active team (prevents stale active_team_id after re-seed)
    await db.users.update_one({"id": user["id"]}, {"$set": {"active_team_id": team_id}})

    demo_athletes = [
        ("João Silva", "Guarda-Redes", 1),
        ("Pedro Costa", "Fixo", 4),
        ("Miguel Santos", "Ala", 7),
        ("Rui Mendes", "Ala", 10),
        ("Tiago Pereira", "Pivô", 9),
        ("André Lopes", "Fixo", 5),
        ("Bruno Ferreira", "Ala", 11),
        ("Carlos Almeida", "Pivô", 8),
    ]
    athlete_ids = []
    for name, pos, num in demo_athletes:
        aid = str(uuid.uuid4())
        athlete_ids.append((aid, name))
        await db.athletes.insert_one({
            "id": aid,
            "team_id": team_id,
            "name": name,
            "position": pos,
            "jersey_number": num,
            "birth_date": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # 45 days of sessions, ~4 per week
    today = date.today()
    random.seed(42)
    sessions_to_insert = []
    for aid, _ in athlete_ids:
        for i in range(45, 0, -1):
            d = today - timedelta(days=i)
            # train Mon/Tue/Thu/Fri (weekdays 0,1,3,4) + match Sat (5) + recovery Sun (6)
            wd = d.weekday()
            train = wd in (0, 1, 3, 4, 5, 6)
            if not train:
                continue
            if random.random() < 0.15:
                continue  # absence
            if wd == 6:
                # recovery — low intensity
                rpe = random.randint(2, 4)
                duration = random.choice([30, 45, 60])
            elif wd == 5:
                rpe = max(1, min(10, 6 + random.randint(-2, 3)))
                duration = 90
            else:
                rpe = max(1, min(10, 5 + random.randint(-2, 3)))
                duration = random.choice([60, 75, 90])
            # spike injection on day 7 to demo high risk
            if i in (5, 6, 7) and random.random() < 0.4 and wd != 6:
                rpe = min(10, rpe + 2)
                duration += 20
            sleep = random.randint(2, 5)
            wellness = random.randint(4, 9)
            # session type mapping by weekday: Sat=match, Tue=gym, Sun=recovery, others=training
            if wd == 5:
                stype = "match"
            elif wd == 1:
                stype = "gym"
            elif wd == 6:
                stype = "recovery"
            else:
                stype = "training"
            sessions_to_insert.append({
                "id": str(uuid.uuid4()),
                "athlete_id": aid,
                "team_id": team_id,
                "date": d.isoformat(),
                "rpe": rpe,
                "duration_min": duration,
                "sleep_quality": sleep,
                "wellness": wellness,
                "session_type": stype,
                "load": rpe * duration,
                "notes": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    if sessions_to_insert:
        await db.sessions.insert_many(sessions_to_insert)

    # seed sample injuries on a couple of athletes
    await db.injuries.delete_many({"team_id": team_id})
    injuries_demo = [
        # athlete index, type, body_part, start_offset_days, end_offset_days_or_none, severity
        (3, "Lesão muscular", "Coxa direita", 95, 70, "medium"),
        (4, "Entorse", "Tornozelo esquerdo", 180, 160, "high"),
        (0, "Contratura", "Lombar", 30, 22, "low"),
    ]
    for ath_idx, typ, body, start_off, end_off, sev in injuries_demo:
        if ath_idx < len(athlete_ids):
            aid, _ = athlete_ids[ath_idx]
            await db.injuries.insert_one({
                "id": str(uuid.uuid4()),
                "athlete_id": aid,
                "team_id": team_id,
                "type": typ,
                "body_part": body,
                "start_date": (today - timedelta(days=start_off)).isoformat(),
                "end_date": (today - timedelta(days=end_off)).isoformat() if end_off else None,
                "severity": sev,
                "notes": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

    # seed a few planned sessions for next 10 days
    await db.planned_sessions.delete_many({"team_id": team_id})
    planned_demo = [
        (1, 6, 75, "Treino técnico-tático", []),
        (2, 7, 90, "Sessão intensiva — pressão alta", []),
        (4, 5, 60, "Recuperação ativa + sets reduzidos", []),
        (6, 8, 90, "Jogo treino vs juniores", []),
        (8, 7, 90, "Simulação de jogo", []),
    ]
    for offset, rpe, dur, notes, aids in planned_demo:
        await db.planned_sessions.insert_one({
            "id": str(uuid.uuid4()),
            "team_id": team_id,
            "date": (today + timedelta(days=offset)).isoformat(),
            "planned_rpe": rpe,
            "planned_duration": dur,
            "planned_load": rpe * dur,
            "notes": notes,
            "athlete_ids": aids,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "ok": True,
        "team_id": team_id,
        "athletes": len(athlete_ids),
        "sessions": len(sessions_to_insert),
        "planned": len(planned_demo),
    }


@api.delete("/seed/demo")
async def clear_data(user=Depends(get_current_user)):
    """Delete current user's ACTIVE team + athletes + sessions + injuries + photos."""
    team = await _get_active_team(user, required=False)
    if team:
        # delete athlete photos
        async for a in db.athletes.find({"team_id": team["id"]}):
            if a.get("photo_path"):
                try:
                    (UPLOAD_DIR / a["photo_path"]).unlink(missing_ok=True)
                except Exception:
                    pass
        await db.sessions.delete_many({"team_id": team["id"]})
        await db.athletes.delete_many({"team_id": team["id"]})
        await db.injuries.delete_many({"team_id": team["id"]})
        await db.planned_sessions.delete_many({"team_id": team["id"]})
        await db.teams.delete_one({"id": team["id"]})
    return {"ok": True}


@api.post("/reset-all")
async def reset_all(user=Depends(get_current_user)):
    """Same as clear_data but explicit endpoint name for the 'reset total' button. Operates on ACTIVE team."""
    team = await _get_active_team(user, required=False)
    counts = {"team": 0, "athletes": 0, "sessions": 0, "injuries": 0, "planned": 0}
    if team:
        async for a in db.athletes.find({"team_id": team["id"]}):
            if a.get("photo_path"):
                try:
                    (UPLOAD_DIR / a["photo_path"]).unlink(missing_ok=True)
                except Exception:
                    pass
        r1 = await db.sessions.delete_many({"team_id": team["id"]})
        r2 = await db.athletes.delete_many({"team_id": team["id"]})
        r3 = await db.injuries.delete_many({"team_id": team["id"]})
        r4 = await db.planned_sessions.delete_many({"team_id": team["id"]})
        await db.teams.delete_one({"id": team["id"]})
        counts = {
            "team": 1,
            "athletes": r2.deleted_count,
            "sessions": r1.deleted_count,
            "injuries": r3.deleted_count,
            "planned": r4.deleted_count,
        }
    return {"ok": True, "deleted": counts}


# ---------------------- Startup ----------------------
@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.teams.create_index("user_id")
    await db.athletes.create_index("team_id")
    await db.sessions.create_index([("athlete_id", 1), ("date", -1)])
    await db.planned_sessions.create_index([("team_id", 1), ("date", 1)])
    await db.injuries.create_index([("team_id", 1), ("athlete_id", 1)])

    # seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "treinador@futsal.pt").lower()
    admin_pwd = os.environ.get("ADMIN_PASSWORD", "treinador123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "password_hash": hash_password(admin_pwd),
            "name": "Treinador Principal",
            "role": "coach",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        if not verify_password(admin_pwd, existing["password_hash"]):
            await db.users.update_one(
                {"email": admin_email},
                {"$set": {"password_hash": hash_password(admin_pwd)}},
            )


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


app.include_router(api)

frontend_url = os.environ.get("FRONTEND_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url] if frontend_url != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
