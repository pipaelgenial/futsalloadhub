from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import asyncio
import logging
import math
import os
import random
import secrets
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import bcrypt
import jwt
import resend
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

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
        if user.get("status") not in (None, "active"):
            raise HTTPException(403, "Conta não ativa")
        user.pop("_id", None)
        user.pop("password_hash", None)
        # Path-based role enforcement
        path = request.url.path
        role = user.get("role", "coach")
        # Player can only access /api/auth/*, /api/player/*, /api/invite/* (and frontend assets)
        if role == "player" and not (
            path.startswith("/api/auth/")
            or path.startswith("/api/player/")
            or path.startswith("/api/invite/")
        ):
            raise HTTPException(403, "Acesso restrito à vista de atleta")
        # Admin can only access /api/auth/* and /api/admin/*
        if role == "admin" and not (
            path.startswith("/api/auth/")
            or path.startswith("/api/admin/")
        ):
            raise HTTPException(403, "Acesso restrito à vista de administrador")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sessão expirada") from None
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido") from None


def require_role(*roles: str):
    """Dependency factory: raises 403 if current user is not in `roles`."""
    async def _dep(user=Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(403, "Acesso não autorizado para este papel")
        return user
    return _dep


require_admin = require_role("admin")
require_player = require_role("player")


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
    load_thresholds: Optional[dict] = None  # {ideal, moderate, high, very_high} per-athlete UA


DEFAULT_LOAD_THRESHOLDS = {"ideal": 300, "moderate": 600, "high": 900, "very_high": 1200}


def _sanitize_thresholds(raw):
    """Validate and normalise load_thresholds dict. Returns dict or None if invalid."""
    if not isinstance(raw, dict):
        return None
    try:
        t = {k: int(raw.get(k)) for k in ("ideal", "moderate", "high", "very_high")}
    except (TypeError, ValueError):
        return None
    # require strictly increasing positive values
    if not (0 < t["ideal"] < t["moderate"] < t["high"] < t["very_high"]):
        return None
    return t


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


VALID_SESSION_TYPES = {"training", "match", "gym", "recovery", "rest", "injury"}


class RestDayIn(BaseModel):
    athlete_id: str
    date: str  # YYYY-MM-DD
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=5)
    wellness: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None


class BulkRestDayIn(BaseModel):
    date: str  # YYYY-MM-DD
    athlete_ids: Optional[List[str]] = None  # None or [] = whole team
    notes: Optional[str] = None


class PlayerRestDayIn(BaseModel):
    date: str
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=5)
    wellness: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None


class InjuryDayIn(BaseModel):
    """Session-level injury entry (NOT the same as full Injury record).
    Marks a single day as injury — counts as 0 UA, dilutes averages like rest.
    """
    athlete_id: str
    date: str  # YYYY-MM-DD
    notes: Optional[str] = None


class PlayerInjuryDayIn(BaseModel):
    date: str
    notes: Optional[str] = None


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
    """Register a new coach. New accounts start as `pending` and require admin validation before login."""
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
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    # Do NOT issue a token — user must be validated by an admin first.
    return {
        "id": user_id,
        "email": email,
        "name": data.name,
        "role": "coach",
        "status": "pending",
        "message": "Conta criada. Aguarda validação por um administrador.",
    }


@api.post("/auth/login")
async def login(data: LoginIn, response: Response):
    email = data.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Credenciais inválidas")
    status = user.get("status", "pending")
    if status == "pending":
        raise HTTPException(403, "A sua conta aguarda validação por um administrador.")
    if status == "suspended":
        raise HTTPException(403, "Conta suspensa. Contacte o administrador.")
    if status != "active":
        raise HTTPException(403, "Conta indisponível")
    token = create_access_token(user["id"], email)
    set_auth_cookie(response, token)
    # Track last login
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"last_login_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {
        "id": user["id"],
        "email": email,
        "name": user.get("name"),
        "role": user.get("role", "coach"),
        "status": status,
        "athlete_id": user.get("athlete_id"),
        "token": token,
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user


# ---------------------- Password Reset (Resend) ----------------------
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")
PASSWORD_RESET_TTL_MIN = 60

if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def _build_reset_email_html(name: str, reset_url: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0A0A0A;font-family:Arial,sans-serif;color:#fff;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0A0A0A;padding:40px 20px;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:#0F0F0F;border:1px solid rgba(255,255,255,0.08);padding:32px;">
        <tr><td>
          <div style="color:#CCFF00;font-size:11px;letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">Futsal Load Hub</div>
          <h1 style="margin:0 0 24px;font-size:28px;color:#fff;">Recuperar a tua password</h1>
          <p style="color:#A3A3A3;line-height:1.6;font-size:14px;">Olá{(' ' + name) if name else ''},</p>
          <p style="color:#A3A3A3;line-height:1.6;font-size:14px;">Recebemos um pedido para redefinires a tua password. Clica no botão abaixo para escolher uma nova:</p>
          <table cellpadding="0" cellspacing="0" style="margin:28px 0;">
            <tr><td style="background:#CCFF00;padding:14px 28px;">
              <a href="{reset_url}" style="color:#000;text-decoration:none;font-weight:bold;font-size:13px;letter-spacing:2px;text-transform:uppercase;">Definir Nova Password</a>
            </td></tr>
          </table>
          <p style="color:#525252;font-size:12px;line-height:1.6;">Ou copia este link no navegador:<br><span style="color:#CCFF00;word-break:break-all;">{reset_url}</span></p>
          <p style="color:#525252;font-size:12px;line-height:1.6;margin-top:24px;">Este link é válido por <strong style="color:#fff;">{PASSWORD_RESET_TTL_MIN} minutos</strong>. Se não pediste a recuperação, podes ignorar este email — a tua password atual continua válida.</p>
          <div style="border-top:1px solid rgba(255,255,255,0.08);margin-top:32px;padding-top:16px;color:#525252;font-size:11px;">Futsal Load Hub · Monitorização de cargas</div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


class ForgotIn(BaseModel):
    email: EmailStr


@api.post("/auth/forgot")
async def forgot_password(data: ForgotIn):
    """Public — generate a password reset token and email the link. Always returns 200 to avoid email enumeration."""
    email = data.email.lower()
    user = await db.users.find_one({"email": email})
    # Silent success even when user not found (no enumeration leak)
    if user and user.get("status") != "suspended":
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MIN)
        # Invalidate any previous tokens for this user
        await db.password_resets.delete_many({"user_id": user["id"]})
        await db.password_resets.insert_one({
            "token": token,
            "user_id": user["id"],
            "email": email,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        base_url = FRONTEND_URL or ""
        reset_url = f"{base_url}/recuperar-password/{token}"
        if RESEND_API_KEY:
            try:
                params = {
                    "from": SENDER_EMAIL,
                    "to": [email],
                    "subject": "Recuperar password — Futsal Load Hub",
                    "html": _build_reset_email_html(user.get("name", ""), reset_url),
                }
                await asyncio.to_thread(resend.Emails.send, params)
            except Exception as e:
                logging.error(f"Resend send failed: {e}")
                # Do not leak to caller
        else:
            logging.warning("RESEND_API_KEY not configured — skipping email send")
    return {"ok": True, "message": "Se o email existir, foi enviado um link de recuperação."}


@api.get("/auth/reset/{token}")
async def validate_reset_token(token: str):
    """Public — check if a reset token is valid before showing the new-password form."""
    record = await db.password_resets.find_one({"token": token}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Link inválido ou já utilizado")
    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        await db.password_resets.delete_one({"token": token})
        raise HTTPException(410, "Link expirado. Pede um novo email de recuperação.")
    return {"email": record["email"]}


class ResetIn(BaseModel):
    password: str = Field(min_length=6)


@api.post("/auth/reset/{token}")
async def reset_password(token: str, data: ResetIn):
    """Public — consume the reset token and set a new password."""
    record = await db.password_resets.find_one({"token": token}, {"_id": 0})
    if not record:
        raise HTTPException(404, "Link inválido ou já utilizado")
    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        await db.password_resets.delete_one({"token": token})
        raise HTTPException(410, "Link expirado. Pede um novo email de recuperação.")
    new_hash = hash_password(data.password)
    await db.users.update_one(
        {"id": record["user_id"]},
        {"$set": {"password_hash": new_hash, "password_updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Consume the token (one-time use)
    await db.password_resets.delete_one({"token": token})
    # Also invalidate any other pending tokens for this user
    await db.password_resets.delete_many({"user_id": record["user_id"]})
    return {"ok": True}


MAX_TEAMS_PER_USER = 5  # platform-wide hard cap; admin can lower per-coach via `max_teams` field
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
        if not team.get("load_thresholds"):
            team["load_thresholds"] = DEFAULT_LOAD_THRESHOLDS
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
        if not t.get("load_thresholds"):
            t["load_thresholds"] = DEFAULT_LOAD_THRESHOLDS
    return teams


@api.post("/teams")
async def create_team(data: TeamIn, user=Depends(get_current_user)):
    """Create a new team. Limit is per-user (`max_teams`, default 5, set by admin)."""
    count = await db.teams.count_documents({"user_id": user["id"]})
    user_limit = int(user.get("max_teams") or MAX_TEAMS_PER_USER)
    user_limit = min(user_limit, MAX_TEAMS_PER_USER)
    if count >= user_limit:
        raise HTTPException(400, f"Limite de {user_limit} equipa(s) atingido para esta conta")
    team_id = str(uuid.uuid4())
    if data.load_thresholds is not None:
        thresholds = _sanitize_thresholds(data.load_thresholds)
        if not thresholds:
            raise HTTPException(400, "Limiares inválidos — devem ser inteiros positivos crescentes")
    else:
        thresholds = DEFAULT_LOAD_THRESHOLDS
    doc = {
        "id": team_id,
        "user_id": user["id"],
        "name": data.name,
        "escalao": data.escalao,
        "epoca": data.epoca,
        "load_thresholds": thresholds,
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
    update_fields = {"name": data.name, "escalao": data.escalao, "epoca": data.epoca}
    if data.load_thresholds is not None:
        thresholds = _sanitize_thresholds(data.load_thresholds)
        if not thresholds:
            raise HTTPException(400, "Limiares inválidos — devem ser inteiros positivos crescentes")
        update_fields["load_thresholds"] = thresholds
    await db.teams.update_one({"id": team_id}, {"$set": update_fields})
    refreshed = await db.teams.find_one({"id": team_id}, {"_id": 0})
    if refreshed and not refreshed.get("load_thresholds"):
        refreshed["load_thresholds"] = DEFAULT_LOAD_THRESHOLDS
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
    # Cascade: linked player user account + any invites
    await db.users.delete_many({"role": "player", "athlete_id": athlete_id})
    await db.invites.delete_many({"athlete_id": athlete_id})
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
    if data.session_type == "rest":
        raise HTTPException(400, "Use o endpoint /api/sessions/rest para marcar folga")
    if data.session_type == "injury":
        raise HTTPException(400, "Use o endpoint /api/sessions/injury para marcar lesão")
    # Prevent registering a normal session on a day already marked as REST or INJURY
    existing_zero = await db.sessions.find_one({
        "athlete_id": data.athlete_id,
        "date": data.date,
        "session_type": {"$in": ["rest", "injury"]},
    })
    if existing_zero:
        kind = "folga" if existing_zero["session_type"] == "rest" else "lesão"
        raise HTTPException(409, f"Este dia está marcado como {kind}. Apaga primeiro antes de registar uma sessão.")
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


@api.post("/sessions/rest")
async def create_rest_day(data: RestDayIn, user=Depends(get_current_user)):
    """Coach registers a REST/OFF day for an athlete.

    Stored as a session with rpe=0, duration_min=0, load=0, session_type='rest'.
    The day still counts in the 28-day ACWR window (as a 0-load day, which is
    the standard sports-science behaviour).
    """
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": data.athlete_id, "team_id": team["id"]})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    # Prevent duplicates for the same athlete/day
    existing = await db.sessions.find_one({
        "athlete_id": data.athlete_id,
        "date": data.date,
    })
    if existing:
        raise HTTPException(409, "Já existe um registo para este atleta nesta data")
    session_id = str(uuid.uuid4())
    doc = {
        "id": session_id,
        "athlete_id": data.athlete_id,
        "team_id": team["id"],
        "date": data.date,
        "rpe": 0,
        "duration_min": 0,
        "sleep_quality": data.sleep_quality,
        "wellness": data.wellness,
        "session_type": "rest",
        "load": 0,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.post("/sessions/injury")
async def create_injury_day(data: InjuryDayIn, user=Depends(get_current_user)):
    """Coach marks a single day as INJURY for an athlete.

    Stored as a 0-UA session (session_type='injury'). Dilutes averages like
    a rest day. Does NOT auto-create an Injury record (use /api/injuries
    endpoints for that).
    """
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": data.athlete_id, "team_id": team["id"]})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    existing = await db.sessions.find_one({
        "athlete_id": data.athlete_id,
        "date": data.date,
    })
    if existing:
        raise HTTPException(409, "Já existe um registo para este atleta nesta data")
    session_id = str(uuid.uuid4())
    doc = {
        "id": session_id,
        "athlete_id": data.athlete_id,
        "team_id": team["id"],
        "date": data.date,
        "rpe": 0,
        "duration_min": 0,
        "sleep_quality": None,
        "wellness": None,
        "session_type": "injury",
        "load": 0,
        "notes": data.notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api.post("/sessions/rest/bulk")
async def create_rest_day_bulk(data: BulkRestDayIn, user=Depends(get_current_user)):
    """Coach marks REST day for the whole team (or a subset).

    Skips athletes that already have any session registered for that date.
    Returns a summary with created/skipped athlete ids and names.
    """
    team = await _get_team_or_404(user)
    # Resolve target athlete list
    if data.athlete_ids:
        target = await db.athletes.find(
            {"id": {"$in": data.athlete_ids}, "team_id": team["id"]},
            {"_id": 0, "id": 1, "name": 1},
        ).to_list(None)
    else:
        target = await db.athletes.find(
            {"team_id": team["id"]},
            {"_id": 0, "id": 1, "name": 1},
        ).to_list(None)
    if not target:
        raise HTTPException(404, "Sem atletas para marcar folga")

    target_ids = [a["id"] for a in target]
    # Find which already have a session that day
    existing_cursor = db.sessions.find(
        {"athlete_id": {"$in": target_ids}, "date": data.date},
        {"_id": 0, "athlete_id": 1},
    )
    existing_ids = {s["athlete_id"] async for s in existing_cursor}

    created = []
    skipped = []
    now_iso = datetime.now(timezone.utc).isoformat()
    docs_to_insert = []
    for a in target:
        if a["id"] in existing_ids:
            skipped.append({"id": a["id"], "name": a["name"]})
            continue
        doc = {
            "id": str(uuid.uuid4()),
            "athlete_id": a["id"],
            "team_id": team["id"],
            "date": data.date,
            "rpe": 0,
            "duration_min": 0,
            "sleep_quality": None,
            "wellness": None,
            "session_type": "rest",
            "load": 0,
            "notes": data.notes,
            "created_at": now_iso,
        }
        docs_to_insert.append(doc)
        created.append({"id": a["id"], "name": a["name"]})
    if docs_to_insert:
        await db.sessions.insert_many(docs_to_insert)
    return {
        "date": data.date,
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": created,
        "skipped": skipped,
    }


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
        if data.session_type == "rest" and existing.get("session_type") != "rest":
            raise HTTPException(400, "Para marcar folga, apaga esta sessão e cria via /sessions/rest")
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


def _aggregate_period(sessions_in_period: list) -> dict:
    """Aggregate stats for a list of sessions (week/month).

    Rest sessions count as 0-load days that DILUTE avg_load (matches the user
    convention: avg_load = total_load / total_days_recorded). Sleep and wellness
    averages exclude None values (rest days typically have no sleep/wellness).

    Returns None for averages when there is no valid data — frontend charts can
    then render gaps instead of misleading zero dips.
    """
    if not sessions_in_period:
        return {"total_load": 0, "avg_load": None, "avg_sleep": None,
                "avg_wellness": None, "sessions": 0, "rest_days": 0}
    rest_count = sum(1 for s in sessions_in_period if s.get("session_type") == "rest")
    total_load = sum(s["load"] for s in sessions_in_period)
    avg_load = round(total_load / len(sessions_in_period), 1)
    sleep_vals = [s["sleep_quality"] for s in sessions_in_period
                  if s.get("sleep_quality") is not None]
    avg_sleep = round(sum(sleep_vals) / len(sleep_vals), 2) if sleep_vals else None
    wellness_vals = [s.get("wellness") for s in sessions_in_period
                     if s.get("wellness") is not None]
    avg_wellness = round(sum(wellness_vals) / len(wellness_vals), 1) if wellness_vals else None
    return {
        "total_load": round(total_load, 1),
        "avg_load": avg_load,
        "avg_sleep": avg_sleep,
        "avg_wellness": avg_wellness,
        "sessions": len(sessions_in_period),
        "rest_days": rest_count,
    }


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

    # Averages — rest days DILUTE avg_load (count in denominator, contributing 0).
    # Rest days count as 0-UA days in the 7/28-day ACWR window (standard convention).
    # Sleep/wellness exclude None values (rest days have no value to average).
    rest_count = sum(1 for s in sessions if s.get("session_type") == "rest")
    avg_load = round(sum(s["load"] for s in sessions) / len(sessions), 1)
    sleep_vals = [s["sleep_quality"] for s in sessions if s.get("sleep_quality") is not None]
    avg_sleep = round(sum(sleep_vals) / len(sleep_vals), 1) if sleep_vals else 0
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
        "rest_days": rest_count,
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
        agg = _aggregate_period(ws)
        total_load = agg["total_load"]
        avg_load = agg["avg_load"]
        avg_sleep = agg["avg_sleep"]
        avg_wellness = agg["avg_wellness"]
        sessions_count = agg["sessions"]
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load and avg_load > 0:
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
            "rest_days": agg["rest_days"],
            "total_load": total_load,
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "avg_wellness": avg_wellness,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    valid = [m for m in weeks_out if m["avg_load"] and m["avg_load"] > 0]
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
        agg = _aggregate_period(ms)
        total_load = agg["total_load"]
        avg_load = agg["avg_load"]
        avg_sleep = agg["avg_sleep"]
        sessions_count = agg["sessions"]
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load and avg_load > 0:
            prev_avg = avg_load
        months_out.append({
            "month": k,
            "sessions": sessions_count,
            "rest_days": agg["rest_days"],
            "total_load": total_load,
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    # overall evolution
    valid = [m for m in months_out if m["avg_load"] and m["avg_load"] > 0]
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
    await _sync_athlete_injury_flag(data.athlete_id, team["id"])
    doc.pop("_id", None)
    return doc


class InjuryUpdate(BaseModel):
    type: Optional[str] = None
    body_part: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None  # set to ISO date to close; empty string or None re-opens
    severity: Optional[str] = None
    notes: Optional[str] = None


@api.put("/injuries/{injury_id}")
async def update_injury(injury_id: str, data: InjuryUpdate, user=Depends(get_current_user)):
    """Update an injury — typically to set `end_date` and close it."""
    team = await _get_team_or_404(user)
    existing = await db.injuries.find_one({"id": injury_id, "team_id": team["id"]})
    if not existing:
        raise HTTPException(404, "Lesão não encontrada")
    update_fields: dict = {}
    if data.type is not None:
        update_fields["type"] = data.type
    if data.body_part is not None:
        update_fields["body_part"] = data.body_part
    if data.start_date is not None:
        update_fields["start_date"] = data.start_date
    # end_date: empty string -> None (reopen); date string -> close; absent -> no change
    if data.end_date is not None:
        update_fields["end_date"] = data.end_date or None
    if data.severity is not None:
        if data.severity not in ("low", "medium", "high"):
            raise HTTPException(400, "Severidade inválida")
        update_fields["severity"] = data.severity
    if data.notes is not None:
        update_fields["notes"] = data.notes
    if update_fields:
        await db.injuries.update_one({"id": injury_id}, {"$set": update_fields})
    await _sync_athlete_injury_flag(existing["athlete_id"], team["id"])
    refreshed = await db.injuries.find_one({"id": injury_id}, {"_id": 0})
    return refreshed


@api.delete("/injuries/{injury_id}")
async def delete_injury(injury_id: str, user=Depends(get_current_user)):
    team = await _get_team_or_404(user)
    existing = await db.injuries.find_one({"id": injury_id, "team_id": team["id"]})
    await db.injuries.delete_one({"id": injury_id, "team_id": team["id"]})
    if existing:
        await _sync_athlete_injury_flag(existing["athlete_id"], team["id"])
    return {"ok": True}


async def _sync_athlete_injury_flag(athlete_id: str, team_id: str) -> None:
    """Set athlete.is_injured = True iff there is any injury without end_date."""
    has_open = await db.injuries.find_one({
        "athlete_id": athlete_id,
        "team_id": team_id,
        "$or": [{"end_date": None}, {"end_date": ""}, {"end_date": {"$exists": False}}],
    })
    await db.athletes.update_one({"id": athlete_id}, {"$set": {"is_injured": bool(has_open)}})


@api.get("/injuries/open")
async def list_open_injuries(user=Depends(get_current_user)):
    """List all CURRENTLY OPEN injuries for the active team (Dashboard widget)."""
    team = await _get_active_team(user, required=False)
    if not team:
        return []
    items = await db.injuries.find({
        "team_id": team["id"],
        "$or": [{"end_date": None}, {"end_date": ""}, {"end_date": {"$exists": False}}],
    }, {"_id": 0}).sort("start_date", -1).to_list(500)
    if not items:
        return []
    athletes = await db.athletes.find({"team_id": team["id"]}, {"_id": 0}).to_list(500)
    a_map = {a["id"]: a for a in athletes}
    for i in items:
        a = a_map.get(i["athlete_id"], {})
        i["athlete_name"] = a.get("name", "—")
        i["athlete_jersey"] = a.get("jersey_number")
        i["athlete_photo_url"] = a.get("photo_url")
    return items


# ---------------------- Alerts (computed on-the-fly) ----------------------
@api.get("/alerts")
async def get_alerts(user=Depends(get_current_user)):
    """Return current high-risk alerts for the active team. Computed on-the-fly.

    Alert ids are stable per (type, athlete_id) so the client can mark them
    as resolved in localStorage. When the underlying issue normalises the
    alert simply disappears from the response.
    """
    team = await _get_active_team(user, required=False)
    if not team:
        return []
    athletes = await db.athletes.find({"team_id": team["id"]}, {"_id": 0}).to_list(200)
    if not athletes:
        return []

    alerts: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for a in athletes:
        sessions = await db.sessions.find({"athlete_id": a["id"]}, {"_id": 0}).to_list(5000)
        m = compute_metrics_for_athlete(sessions)
        last = max(sessions, key=lambda s: s["date"]) if sessions else None
        ath_name = a["name"]

        # ---- ACWR ----
        if m["acwr_zone"] == "high_risk":
            alerts.append({
                "id": f"acwr_high_{a['id']}",
                "type": "acwr_high",
                "severity": "danger",
                "athlete_id": a["id"], "athlete_name": ath_name,
                "title": "ACWR em alto risco",
                "message": f"ACWR {m['acwr']:.2f} ≥ 1.5 — risco elevado de lesão",
                "value": m["acwr"], "threshold": 1.5,
                "created_at": now_iso,
            })
        elif m["acwr_zone"] == "detraining" and m.get("sufficient_data"):
            alerts.append({
                "id": f"acwr_low_{a['id']}",
                "type": "acwr_low",
                "severity": "warning",
                "athlete_id": a["id"], "athlete_name": ath_name,
                "title": "Destreinamento",
                "message": f"ACWR {m['acwr']:.2f} < 0.8 — carga insuficiente",
                "value": m["acwr"], "threshold": 0.8,
                "created_at": now_iso,
            })

        # ---- Monotonia ----
        if m["monotony_zone"] == "critical":
            alerts.append({
                "id": f"monotony_critical_{a['id']}",
                "type": "monotony_critical",
                "severity": "danger",
                "athlete_id": a["id"], "athlete_name": ath_name,
                "title": "Monotonia crítica",
                "message": f"Monotonia {m['monotony']:.2f} > 2.0 — treinos sem variação",
                "value": m["monotony"], "threshold": 2.0,
                "created_at": now_iso,
            })

        # ---- Strain extremo ----
        if m["strain_zone"] == "extreme":
            alerts.append({
                "id": f"strain_extreme_{a['id']}",
                "type": "strain_extreme",
                "severity": "danger",
                "athlete_id": a["id"], "athlete_name": ath_name,
                "title": "Strain extremo",
                "message": f"Strain {m['strain']:.0f} > 6000 — sobrecarga semanal",
                "value": m["strain"], "threshold": 6000,
                "created_at": now_iso,
            })

        # ---- Última sessão: sono e bem-estar ----
        if last:
            sq = last.get("sleep_quality")
            if sq is not None and sq <= 2:
                alerts.append({
                    "id": f"sleep_poor_{a['id']}",
                    "type": "sleep_poor",
                    "severity": "warning",
                    "athlete_id": a["id"], "athlete_name": ath_name,
                    "title": "Sono muito mau",
                    "message": f"Última sessão ({last['date']}): qualidade do sono {sq}/5",
                    "value": sq, "threshold": 2,
                    "created_at": now_iso,
                })
            w = last.get("wellness")
            if w is not None and w <= 3:
                alerts.append({
                    "id": f"wellness_low_{a['id']}",
                    "type": "wellness_low",
                    "severity": "warning",
                    "athlete_id": a["id"], "athlete_name": ath_name,
                    "title": "Bem-estar muito baixo",
                    "message": f"Última sessão ({last['date']}): bem-estar {w}/10",
                    "value": w, "threshold": 3,
                    "created_at": now_iso,
                })

    # ---- Lesões abertas ----
    injuries = await db.injuries.find({"team_id": team["id"]}, {"_id": 0}).to_list(500)
    ath_name_map = {a["id"]: a["name"] for a in athletes}
    for inj in injuries:
        if inj.get("end_date"):
            continue  # already recovered
        ath_id = inj.get("athlete_id")
        alerts.append({
            "id": f"injury_open_{inj['id']}",
            "type": "injury_open",
            "severity": "danger" if inj.get("severity") == "high" else "warning",
            "athlete_id": ath_id,
            "athlete_name": ath_name_map.get(ath_id, "Atleta"),
            "title": "Lesão em curso",
            "message": f"{inj.get('type', 'Lesão')} — {inj.get('body_part', 'n/a')} (desde {inj.get('start_date', '')})",
            "value": inj.get("severity", "low"),
            "threshold": None,
            "created_at": now_iso,
        })

    severity_order = {"danger": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda x: (severity_order.get(x["severity"], 9), x.get("athlete_name", "")))
    return alerts


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
async def calendar_view(start: str, days: int = 28, athlete_id: Optional[str] = None, user=Depends(get_current_user)):
    """Day-by-day aggregate of recorded sessions and planned sessions.

    If `athlete_id` is provided, restrict the view to that athlete only.
    Otherwise show the full team aggregate.
    """
    team = await _get_active_team(user, required=False)
    if team:
        team = {k: v for k, v in team.items() if k != "_id"}
    if not team:
        return {"team": None, "days": []}
    start_d = _parse_date(start)
    end_d = start_d + timedelta(days=days - 1)
    end_iso = end_d.isoformat()
    s_filter = {"team_id": team["id"], "date": {"$gte": start, "$lte": end_iso}}
    p_filter = {"team_id": team["id"], "date": {"$gte": start, "$lte": end_iso}}
    if athlete_id:
        # Validate athlete belongs to this team
        owns = await db.athletes.count_documents({"id": athlete_id, "team_id": team["id"]})
        if not owns:
            raise HTTPException(404, "Atleta não encontrado")
        s_filter["athlete_id"] = athlete_id
        # planned sessions: keep team-wide (athlete_ids None/[] = whole team) or
        # those that explicitly include this athlete
        p_filter = {
            "team_id": team["id"],
            "date": {"$gte": start, "$lte": end_iso},
            "$or": [
                {"athlete_ids": {"$in": [athlete_id]}},
                {"athlete_ids": {"$exists": False}},
                {"athlete_ids": None},
                {"athlete_ids": []},
            ],
        }
    sessions = await db.sessions.find(s_filter, {"_id": 0}).to_list(5000)
    planned = await db.planned_sessions.find(p_filter, {"_id": 0}).to_list(1000)
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
        agg = _aggregate_period(ws)
        total_load = agg["total_load"]
        avg_load = agg["avg_load"]
        avg_sleep = agg["avg_sleep"]
        avg_wellness = agg["avg_wellness"]
        sessions_count = agg["sessions"]
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load and avg_load > 0:
            prev_avg = avg_load
        y, w = k.split("-W")
        start_d = _week_start(int(y), int(w))
        weeks_out.append({
            "week": k,
            "label": _format_week_label(k),
            "start_date": start_d.isoformat(),
            "end_date": (start_d + timedelta(days=6)).isoformat(),
            "sessions": sessions_count,
            "rest_days": agg["rest_days"],
            "total_load": total_load,
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "avg_wellness": avg_wellness,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    valid = [m for m in weeks_out if m["avg_load"] and m["avg_load"] > 0]
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
        agg = _aggregate_period(ms)
        total_load = agg["total_load"]
        avg_load = agg["avg_load"]
        avg_sleep = agg["avg_sleep"]
        sessions_count = agg["sessions"]
        delta = None
        delta_pct = None
        if prev_avg is not None and prev_avg > 0 and avg_load and avg_load > 0:
            delta = round(avg_load - prev_avg, 1)
            delta_pct = round((avg_load - prev_avg) / prev_avg * 100, 1)
        if avg_load and avg_load > 0:
            prev_avg = avg_load
        months_out.append({
            "month": k,
            "sessions": sessions_count,
            "rest_days": agg["rest_days"],
            "total_load": total_load,
            "avg_load": avg_load,
            "avg_sleep": avg_sleep,
            "delta_load": delta,
            "delta_load_pct": delta_pct,
        })

    valid = [m for m in months_out if m["avg_load"] and m["avg_load"] > 0]
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
    # Pick 3 athletes to be at HIGH/CRITICAL risk for demo (ACWR > 1.5,
    # monotony > 2.0, strain > 6000, poor sleep/wellness).
    high_risk_idx = {0, 2, 5}  # Miguel, Tiago, Bruno (3 of 8)
    sessions_to_insert = []
    for idx, (aid, _) in enumerate(athlete_ids):
        is_high_risk = idx in high_risk_idx
        for i in range(45, 0, -1):
            d = today - timedelta(days=i)
            wd = d.weekday()
            train = wd in (0, 1, 3, 4, 5, 6)
            if not train:
                continue
            if random.random() < 0.15:
                continue  # absence
            # ---- Baseline by weekday ----
            if wd == 6:
                rpe = random.randint(2, 4)
                duration = random.choice([30, 45, 60])
                stype = "recovery"
            elif wd == 5:
                rpe = max(1, min(10, 6 + random.randint(-2, 3)))
                duration = 90
                stype = "match"
            elif wd == 1:
                rpe = max(1, min(10, 5 + random.randint(-2, 3)))
                duration = random.choice([60, 75, 90])
                stype = "gym"
            else:
                rpe = max(1, min(10, 5 + random.randint(-2, 3)))
                duration = random.choice([60, 75, 90])
                stype = "training"
            sleep = random.randint(2, 5)
            wellness = random.randint(4, 9)
            # ---- HIGH RISK INJECTION (last 7 days only - acute spike) ----
            # Sharp increase in ACUTE load (last 7 days) while CHRONIC (28d) stays normal.
            # Also low variance for monotony, poor sleep/wellness.
            if is_high_risk and i <= 7 and wd != 6:
                # Very high & uniform → ACWR >>1.5, monotony >>2.0, strain >>6000
                rpe = random.choice([9, 9, 10, 10])
                duration = random.choice([100, 110, 115, 120])
                sleep = random.randint(1, 2)
                wellness = random.randint(2, 4)
            # ---- Mild spike injection (other athletes, last week) ----
            elif not is_high_risk and i in (5, 6, 7) and random.random() < 0.4 and wd != 6:
                rpe = min(10, rpe + 2)
                duration += 20
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


# ============================================================
# ADMIN ENDPOINTS — manage user accounts (validate/suspend/delete)
# ============================================================
@api.get("/admin/users")
async def admin_list_users(admin=Depends(require_admin)):
    """List all users with summary stats. Admin only."""
    users = await db.users.find({}, {"password_hash": 0, "_id": 0}).sort("created_at", 1).to_list(500)
    out = []
    for u in users:
        teams_n = await db.teams.count_documents({"user_id": u["id"]})
        athletes_n = 0
        sessions_n = 0
        if teams_n:
            team_ids = [t["id"] async for t in db.teams.find({"user_id": u["id"]}, {"id": 1})]
            athletes_n = await db.athletes.count_documents({"team_id": {"$in": team_ids}})
            sessions_n = await db.sessions.count_documents({"team_id": {"$in": team_ids}})
        # ensure max_teams default
        if "max_teams" not in u and u.get("role") == "coach":
            u["max_teams"] = MAX_TEAMS_PER_USER
        out.append({
            **u,
            "stats": {"teams": teams_n, "athletes": athletes_n, "sessions": sessions_n},
        })
    return out


class MaxTeamsIn(BaseModel):
    max_teams: int = Field(ge=1, le=MAX_TEAMS_PER_USER)


@api.post("/admin/users/{user_id}/max-teams")
async def admin_set_max_teams(user_id: str, data: MaxTeamsIn, admin=Depends(require_admin)):
    """Admin defines how many teams a coach may create (1..5)."""
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "Utilizador não encontrado")
    if target.get("role") != "coach":
        raise HTTPException(400, "Apenas aplicável a contas de treinador")
    await db.users.update_one({"id": user_id}, {"$set": {"max_teams": data.max_teams}})
    return {"ok": True, "id": user_id, "max_teams": data.max_teams}


@api.post("/admin/users/{user_id}/validate")
async def admin_validate_user(user_id: str, admin=Depends(require_admin)):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "Utilizador não encontrado")
    if target.get("role") == "admin":
        raise HTTPException(400, "Não é possível alterar status de um admin")
    await db.users.update_one({"id": user_id}, {"$set": {"status": "active"}})
    return {"ok": True, "id": user_id, "status": "active"}


@api.post("/admin/users/{user_id}/suspend")
async def admin_suspend_user(user_id: str, admin=Depends(require_admin)):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "Utilizador não encontrado")
    if target.get("role") == "admin":
        raise HTTPException(400, "Não é possível suspender um admin")
    await db.users.update_one({"id": user_id}, {"$set": {"status": "suspended"}})
    return {"ok": True, "id": user_id, "status": "suspended"}


@api.post("/admin/users/{user_id}/reactivate")
async def admin_reactivate_user(user_id: str, admin=Depends(require_admin)):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "Utilizador não encontrado")
    await db.users.update_one({"id": user_id}, {"$set": {"status": "active"}})
    return {"ok": True, "id": user_id, "status": "active"}


@api.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin=Depends(require_admin)):
    """Cascading delete: removes the user and ALL their data (teams, athletes, sessions, injuries, invites)."""
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(404, "Utilizador não encontrado")
    if target.get("role") == "admin":
        raise HTTPException(400, "Não é possível eliminar uma conta de admin")

    if target.get("role") == "player":
        # Player account: only delete invite link (athlete stays under coach)
        await db.invites.update_many({"player_user_id": user_id}, {"$unset": {"player_user_id": ""}})
        await db.users.delete_one({"id": user_id})
        return {"ok": True}

    # Coach: cascade everything
    team_ids = [t["id"] async for t in db.teams.find({"user_id": user_id}, {"id": 1})]
    athlete_ids = []
    if team_ids:
        athlete_ids = [a["id"] async for a in db.athletes.find({"team_id": {"$in": team_ids}}, {"id": 1})]
    if athlete_ids:
        await db.sessions.delete_many({"athlete_id": {"$in": athlete_ids}})
        await db.injuries.delete_many({"athlete_id": {"$in": athlete_ids}})
        await db.invites.delete_many({"athlete_id": {"$in": athlete_ids}})
        # Delete player users linked to these athletes
        await db.users.delete_many({"role": "player", "athlete_id": {"$in": athlete_ids}})
        await db.athletes.delete_many({"id": {"$in": athlete_ids}})
    if team_ids:
        await db.planned_sessions.delete_many({"team_id": {"$in": team_ids}})
        await db.teams.delete_many({"id": {"$in": team_ids}})
    await db.users.delete_one({"id": user_id})
    return {"ok": True}


# ============================================================
# ATHLETE INVITE ENDPOINTS
# ============================================================
def _generate_invite_token() -> str:
    """Short URL-safe token (24 chars) for athlete invites."""
    import secrets
    return secrets.token_urlsafe(18)


@api.post("/athletes/{athlete_id}/invite")
async def create_or_refresh_invite(athlete_id: str, user=Depends(get_current_user)):
    """Coach generates (or refreshes) the invite link for an athlete. Returns the token + full URL."""
    if user.get("role") != "coach":
        raise HTTPException(403, "Apenas treinadores podem gerar convites")
    team = await _get_team_or_404(user)
    athlete = await db.athletes.find_one({"id": athlete_id, "team_id": team["id"]}, {"_id": 0})
    if not athlete:
        raise HTTPException(404, "Atleta não encontrado")
    # Check if there's already a linked player account
    linked_player = await db.users.find_one({"role": "player", "athlete_id": athlete_id})
    if linked_player:
        return {
            "linked": True,
            "player_email": linked_player.get("email"),
            "athlete_id": athlete_id,
        }
    # (Re)issue a token — delete any previous unused invite
    await db.invites.delete_many({"athlete_id": athlete_id})
    token = _generate_invite_token()
    await db.invites.insert_one({
        "token": token,
        "athlete_id": athlete_id,
        "team_id": team["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    base_url = os.environ.get("FRONTEND_PUBLIC_URL", "").rstrip("/")
    url = f"{base_url}/convite/{token}" if base_url else f"/convite/{token}"
    return {"linked": False, "token": token, "url": url, "athlete_id": athlete_id, "athlete_name": athlete["name"]}


@api.get("/invite/{token}")
async def get_invite_info(token: str):
    """Public — returns athlete and team info for the invite landing page."""
    invite = await db.invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Convite inválido ou expirado")
    athlete = await db.athletes.find_one({"id": invite["athlete_id"]}, {"_id": 0})
    team = await db.teams.find_one({"id": invite["team_id"]}, {"_id": 0})
    if not athlete or not team:
        raise HTTPException(404, "Convite associado a dados eliminados")
    # If a player account already linked, invite is consumed
    linked = await db.users.find_one({"role": "player", "athlete_id": invite["athlete_id"]})
    if linked:
        raise HTTPException(410, "Este convite já foi utilizado")
    return {
        "athlete_name": athlete["name"],
        "athlete_id": athlete["id"],
        "team_name": team["name"],
        "team_escalao": team.get("escalao"),
    }


class InviteAcceptIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: Optional[str] = None


@api.post("/invite/{token}/accept")
async def accept_invite(token: str, data: InviteAcceptIn, response: Response):
    """Public — player creates their account using the invite token. Auto-activated, no admin step."""
    invite = await db.invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(404, "Convite inválido ou expirado")
    # Ensure the athlete still exists
    athlete = await db.athletes.find_one({"id": invite["athlete_id"]}, {"_id": 0})
    if not athlete:
        raise HTTPException(404, "Atleta associado já não existe")
    # Ensure no player linked yet
    linked = await db.users.find_one({"role": "player", "athlete_id": invite["athlete_id"]})
    if linked:
        raise HTTPException(410, "Este convite já foi utilizado")
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email já registado")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(data.password),
        "name": data.name or athlete["name"],
        "role": "player",
        "status": "active",
        "athlete_id": invite["athlete_id"],
        "team_id": invite["team_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    await db.invites.update_one({"token": token}, {"$set": {"player_user_id": user_id, "accepted_at": datetime.now(timezone.utc).isoformat()}})
    access = create_access_token(user_id, email)
    set_auth_cookie(response, access)
    return {
        "id": user_id,
        "email": email,
        "name": doc["name"],
        "role": "player",
        "status": "active",
        "athlete_id": invite["athlete_id"],
        "token": access,
    }


# ============================================================
# PLAYER ENDPOINTS — restricted to own data
# ============================================================
@api.get("/player/me")
async def player_me(user=Depends(require_player)):
    """Returns the player's athlete + team info (name, position, team)."""
    athlete = await db.athletes.find_one({"id": user["athlete_id"]}, {"_id": 0}) if user.get("athlete_id") else None
    team = await db.teams.find_one({"id": user["team_id"]}, {"_id": 0}) if user.get("team_id") else None
    return {
        "user": user,
        "athlete": athlete,
        "team": {"name": team.get("name"), "escalao": team.get("escalao"), "epoca": team.get("epoca")} if team else None,
    }


@api.get("/player/sessions")
async def player_list_sessions(user=Depends(require_player)):
    """List the player's own sessions, NEWEST FIRST, without computed load fields."""
    if not user.get("athlete_id"):
        return []
    cursor = db.sessions.find({"athlete_id": user["athlete_id"]}, {"_id": 0}).sort("date", -1)
    out = []
    async for s in cursor:
        # Strip load info from player view per requirement (B = hide carga completely)
        out.append({
            "id": s["id"],
            "date": s["date"],
            "session_type": s.get("session_type", "training"),
            "rpe": s.get("rpe"),
            "duration_min": s.get("duration_min"),
            "sleep_quality": s.get("sleep_quality"),
            "wellness": s.get("wellness"),
            "notes": s.get("notes"),
        })
    return out


class PlayerSessionIn(BaseModel):
    date: str
    session_type: str = "training"
    rpe: int = Field(ge=1, le=10)
    duration_min: int = Field(ge=1, le=600)
    sleep_quality: Optional[int] = Field(default=None, ge=1, le=5)
    wellness: Optional[int] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None


@api.post("/player/sessions")
async def player_create_session(data: PlayerSessionIn, user=Depends(require_player)):
    """Player registers their OWN session (no athlete_id override possible).

    Players CANNOT delete their own sessions — only the coach (via /api/sessions/{id})
    can edit/delete them. This preserves the integrity of the load data.
    """
    if not user.get("athlete_id") or not user.get("team_id"):
        raise HTTPException(400, "Conta sem atleta associado")
    if data.session_type not in {"training", "match", "gym", "recovery"}:
        raise HTTPException(400, "Tipo de sessão inválido")
    # Prevent registering a normal session on a day already marked as REST or INJURY
    rest_existing = await db.sessions.find_one({
        "athlete_id": user["athlete_id"],
        "date": data.date,
        "session_type": {"$in": ["rest", "injury"]},
    })
    if rest_existing:
        kind = "folga" if rest_existing["session_type"] == "rest" else "lesão"
        raise HTTPException(409, f"Este dia está marcado como {kind}. Apaga primeiro antes de registar uma sessão.")
    load = int(data.rpe) * int(data.duration_min)
    session_id = str(uuid.uuid4())
    doc = {
        "id": session_id,
        "athlete_id": user["athlete_id"],
        "team_id": user["team_id"],
        "date": data.date,
        "session_type": data.session_type,
        "rpe": data.rpe,
        "duration_min": data.duration_min,
        "load": load,
        "sleep_quality": data.sleep_quality,
        "wellness": data.wellness,
        "notes": data.notes,
        "created_by": "player",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sessions.insert_one(doc)
    # Return WITHOUT load
    return {k: v for k, v in doc.items() if k not in {"load", "_id"}}


@api.post("/player/sessions/rest")
async def player_create_rest_day(data: PlayerRestDayIn, user=Depends(require_player)):
    """Player marks today/a date as a REST day. No load, no rpe.

    Counts as a 0-load day in the 28-day ACWR window (sports-science default).
    """
    if not user.get("athlete_id") or not user.get("team_id"):
        raise HTTPException(400, "Conta sem atleta associado")
    existing = await db.sessions.find_one({
        "athlete_id": user["athlete_id"],
        "date": data.date,
    })
    if existing:
        raise HTTPException(409, "Já existe um registo para este dia")
    session_id = str(uuid.uuid4())
    doc = {
        "id": session_id,
        "athlete_id": user["athlete_id"],
        "team_id": user["team_id"],
        "date": data.date,
        "session_type": "rest",
        "rpe": 0,
        "duration_min": 0,
        "load": 0,
        "sleep_quality": data.sleep_quality,
        "wellness": data.wellness,
        "notes": data.notes,
        "created_by": "player",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sessions.insert_one(doc)
    return {k: v for k, v in doc.items() if k not in {"load", "_id"}}


@api.post("/player/sessions/injury")
async def player_create_injury_day(data: PlayerInjuryDayIn, user=Depends(require_player)):
    """Player marks a date as INJURY (no load, dilutes averages like rest)."""
    if not user.get("athlete_id") or not user.get("team_id"):
        raise HTTPException(400, "Conta sem atleta associado")
    existing = await db.sessions.find_one({
        "athlete_id": user["athlete_id"],
        "date": data.date,
    })
    if existing:
        raise HTTPException(409, "Já existe um registo para este dia")
    session_id = str(uuid.uuid4())
    doc = {
        "id": session_id,
        "athlete_id": user["athlete_id"],
        "team_id": user["team_id"],
        "date": data.date,
        "session_type": "injury",
        "rpe": 0,
        "duration_min": 0,
        "load": 0,
        "sleep_quality": None,
        "wellness": None,
        "notes": data.notes,
        "created_by": "player",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.sessions.insert_one(doc)
    return {k: v for k, v in doc.items() if k not in {"load", "_id"}}


# ============================================================
# EXPORTS — CSV (sessions) + PDF (weekly/monthly summaries)
# ============================================================
import csv as _csv
import io

from fastapi.responses import StreamingResponse


@api.get("/export/sessions.csv")
async def export_sessions_csv(
    start: Optional[str] = None,
    end: Optional[str] = None,
    user=Depends(get_current_user),
):
    """Coach exports team sessions in a date range as CSV.
    Filename: sessoes_{team_slug}_{start}_{end}.csv
    Columns: data, atleta, dorsal, posição, tipo, RPE, duração (min), carga (UA), sono (1-5), bem-estar (1-10), notas
    """
    if user.get("role") != "coach":
        raise HTTPException(403, "Apenas treinadores podem exportar")
    team = await _get_team_or_404(user)
    q = {"team_id": team["id"]}
    if start and end:
        q["date"] = {"$gte": start, "$lte": end}
    sessions = await db.sessions.find(q, {"_id": 0}).sort("date", 1).to_list(20000)
    athletes = await db.athletes.find({"team_id": team["id"]}, {"_id": 0}).to_list(500)
    a_map = {a["id"]: a for a in athletes}

    type_label = {"training": "Treino", "match": "Jogo", "gym": "Ginásio", "recovery": "Recuperação", "rest": "Folga", "injury": "Lesão"}
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM so Excel reads UTF-8 correctly
    writer = _csv.writer(buf, delimiter=";")
    writer.writerow(["Data", "Atleta", "Dorsal", "Posição", "Tipo", "RPE", "Duração (min)", "Carga (UA)", "Sono (1-5)", "Bem-estar (1-10)", "Notas"])
    for s in sessions:
        a = a_map.get(s["athlete_id"], {})
        writer.writerow([
            s.get("date", ""),
            a.get("name", "—"),
            a.get("jersey_number", "") or "",
            a.get("position", "") or "",
            type_label.get(s.get("session_type", "training"), s.get("session_type", "")),
            s.get("rpe", ""),
            s.get("duration_min", ""),
            s.get("load", ""),
            s.get("sleep_quality", ""),
            s.get("wellness", ""),
            (s.get("notes") or "").replace("\n", " "),
        ])
    buf.seek(0)
    safe_team = "".join(c if c.isalnum() else "_" for c in team["name"])[:40]
    fname = f"sessoes_{safe_team}_{start or 'inicio'}_{end or 'fim'}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _build_summary_pdf(*, title: str, athlete_name: str, team_name: str, period_label: str, rows: list, headers: list, evolution: str, evolution_pct: float) -> bytes:
    """Generate a styled PDF summary using reportlab. Returns the bytes."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    lime = colors.HexColor("#7AAA00")
    dark = colors.HexColor("#0F0F0F")
    grey = colors.HexColor("#525252")
    light = colors.HexColor("#A3A3A3")

    h_style = ParagraphStyle("h", parent=styles["Title"], textColor=dark, fontSize=22, leading=26, spaceAfter=4)
    sub_style = ParagraphStyle("sub", parent=styles["Normal"], textColor=lime, fontSize=9, spaceAfter=2, leading=12)
    meta_style = ParagraphStyle("meta", parent=styles["Normal"], textColor=grey, fontSize=10, spaceAfter=16, leading=14)
    body_style = ParagraphStyle("body", parent=styles["Normal"], textColor=dark, fontSize=11, spaceAfter=8, leading=15)

    story = []
    story.append(Paragraph("FUTSAL LOAD HUB · " + title.upper(), sub_style))
    story.append(Paragraph(athlete_name, h_style))
    story.append(Paragraph(f"{team_name} · {period_label}", meta_style))

    if rows:
        ev_color = "#7AAA00" if evolution == "subiu" else ("#C24500" if evolution == "desceu" else "#525252")
        story.append(Paragraph(
            f'Evolução da carga: <font color="{ev_color}"><b>{evolution.upper()}</b> ({evolution_pct:+.1f}%)</font>',
            body_style,
        ))

    table_data = [headers] + rows if rows else [headers, ["—"] * len(headers)]
    tbl = Table(table_data, repeatRows=1, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), lime),
        ("TEXTCOLOR", (0, 0), (-1, 0), dark),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
        ("TEXTCOLOR", (0, 1), (-1, -1), dark),
        ("GRID", (0, 0), (-1, -1), 0.5, light),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f'Gerado em {datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")} UTC · futsal-load-hub',
        ParagraphStyle("foot", parent=styles["Normal"], textColor=grey, fontSize=8, alignment=2),
    ))

    doc.build(story)
    return buf.getvalue()


@api.get("/export/weekly/{athlete_id}.pdf")
async def export_weekly_pdf(athlete_id: str, weeks: int = 8, user=Depends(get_current_user)):
    if user.get("role") != "coach":
        raise HTTPException(403, "Apenas treinadores podem exportar")
    data = await weekly_summary(athlete_id, weeks=weeks, user=user)
    rows = []
    for w in data["weeks"]:
        delta_str = ""
        if w.get("delta_load_pct") is not None:
            sign = "+" if w["delta_load_pct"] > 0 else ""
            delta_str = f"{sign}{w['delta_load_pct']:.1f}%"
        rows.append([
            w.get("label", w["week"]),
            str(w.get("sessions", 0)),
            f'{w.get("avg_load", 0):.0f}',
            f'{w.get("avg_sleep", 0):.1f}' if w.get("avg_sleep") else "—",
            f'{w.get("avg_wellness", 0):.1f}' if w.get("avg_wellness") else "—",
            delta_str,
        ])
    team = await _get_team_or_404(user)
    pdf_bytes = _build_summary_pdf(
        title="Resumo Semanal",
        athlete_name=data["athlete"]["name"],
        team_name=team["name"],
        period_label=f"Últimas {weeks} semanas",
        rows=rows,
        headers=["Semana", "Sessões", "Carga méd.", "Sono", "Bem-estar", "Δ vs sem. anterior"],
        evolution=data.get("evolution", "indeterminado"),
        evolution_pct=data.get("evolution_pct", 0),
    )
    safe_name = "".join(c if c.isalnum() else "_" for c in data["athlete"]["name"])[:40]
    fname = f"semanal_{safe_name}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api.get("/export/monthly/{athlete_id}.pdf")
async def export_monthly_pdf(athlete_id: str, months: int = 6, user=Depends(get_current_user)):
    if user.get("role") != "coach":
        raise HTTPException(403, "Apenas treinadores podem exportar")
    data = await monthly_summary(athlete_id, months=months, user=user)
    rows = []
    for m in data["months"]:
        delta_str = ""
        if m.get("delta_load_pct") is not None:
            sign = "+" if m["delta_load_pct"] > 0 else ""
            delta_str = f"{sign}{m['delta_load_pct']:.1f}%"
        rows.append([
            m.get("month", ""),
            str(m.get("sessions", 0)),
            f'{m.get("avg_load", 0):.0f}',
            f'{m.get("avg_sleep", 0):.1f}' if m.get("avg_sleep") else "—",
            delta_str,
        ])
    team = await _get_team_or_404(user)
    pdf_bytes = _build_summary_pdf(
        title="Resumo Mensal",
        athlete_name=data["athlete"]["name"],
        team_name=team["name"],
        period_label=f"Últimos {months} meses",
        rows=rows,
        headers=["Mês", "Sessões", "Carga méd.", "Sono", "Δ vs mês anterior"],
        evolution=data.get("evolution", "indeterminado"),
        evolution_pct=data.get("evolution_pct", 0),
    )
    safe_name = "".join(c if c.isalnum() else "_" for c in data["athlete"]["name"])[:40]
    fname = f"mensal_{safe_name}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ---------------------- Startup ----------------------
@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.teams.create_index("user_id")
    await db.athletes.create_index("team_id")
    await db.sessions.create_index([("athlete_id", 1), ("date", -1)])
    await db.planned_sessions.create_index([("team_id", 1), ("date", 1)])
    await db.injuries.create_index([("team_id", 1), ("athlete_id", 1)])
    await db.invites.create_index("token", unique=True)
    await db.invites.create_index("athlete_id")
    await db.password_resets.create_index("token", unique=True)
    await db.password_resets.create_index("user_id")

    # --- Migration: add role/status defaults for legacy users ---
    await db.users.update_many(
        {"role": {"$exists": False}},
        {"$set": {"role": "coach"}},
    )
    await db.users.update_many(
        {"status": {"$exists": False}},
        {"$set": {"status": "pending"}},
    )

    # --- Bootstrap admin account ---
    ADMIN_BOOTSTRAP_EMAIL = "pedrompsantos84@gmail.com"
    ADMIN_BOOTSTRAP_PWD = "amarense"
    existing_admin = await db.users.find_one({"email": ADMIN_BOOTSTRAP_EMAIL})
    if not existing_admin:
        await db.users.insert_one({
            "id": str(uuid.uuid4()),
            "email": ADMIN_BOOTSTRAP_EMAIL,
            "password_hash": hash_password(ADMIN_BOOTSTRAP_PWD),
            "name": "Administrador",
            "role": "admin",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        # Ensure admin role + active status are enforced
        await db.users.update_one(
            {"email": ADMIN_BOOTSTRAP_EMAIL},
            {"$set": {"role": "admin", "status": "active"}},
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
