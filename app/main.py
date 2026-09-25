import base64
import json
import os
import sqlite3
import secrets
import io
import re
import unicodedata
import csv
import shutil
import socket
import zipfile
from math import ceil
from datetime import datetime, timedelta, timezone
import ipaddress
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .database import connection, database_path, init_db
from .schemas import (
    BranchInput, CustomerIdentifyInput, LoginInput, LoyaltyProgramInput,
    OperationTokenInput, RewardBatchInput, TenantInput, TenantUpdate, UserInput, ValidateOperationInput, LoyaltyProgramUpdate, LoyaltyProgramStatusUpdate,
    ServiceSettingsInput, CopyServiceSettingsInput, UserUpdate, UserStatusInput,
    PasswordChangeInput, SupportCodeInput, SupportResetInput, AssistedCustomerInput,
    CustomerMetaInput, MergeCustomersInput, RestoreBackupInput, ResetPlatformInput,
    AppointmentServiceInput, AppointmentServiceStatusInput, AppointmentBookingInput,
    AppointmentStatusInput, AppointmentCancelInput, AppointmentDelayInput,
    BrandingInput, BrandingLogoInput, BrandingBackgroundInput, ProgramIconInput,
    TimeServiceInput, TimeServiceStatusInput, TimeSessionStartInput, TimeSessionCloseInput,
    RaffleInput, RaffleTicketInput, RaffleStatusInput, RouletteInput, RouletteStatusInput, ModuleSettingsInput,
    NotificationSendInput, PushSubscriptionInput, CollaborationContactInput, CollaborationCreateInput, CollaborationUpdateInput, CollaborationStatusInput, CollaborationActiveInput, WorkerAccessInput, PlatformAdInput, BusinessAdInput, BirthdaySettingsInput,
)
from .security import create_customer_token, create_token, decode_token, hash_password, verify_password

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ALLOWED_ROLES = {"super_admin", "business_admin", "branch_admin", "worker"}

app = FastAPI(title="NEGROSKY LOYALTY V3", version="3.0.55")
app.mount("/static", StaticFiles(directory=WEB), name="static")

@app.middleware("http")
async def no_browser_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def row_dict(row):
    return dict(row) if row else None


def new_operation_code(con):
    for _ in range(20):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if not con.execute("SELECT 1 FROM operation_tokens WHERE code=?", (code,)).fetchone() and not con.execute("SELECT 1 FROM raffle_operation_tokens WHERE code=?", (code,)).fetchone():
            return code
    raise HTTPException(status_code=503, detail="No fue posible generar el código. Intenta de nuevo.")


def program_stock(data):
    if data.reward_display == "quantity" and data.reward_stock is None:
        raise HTTPException(status_code=422, detail="Indica la cantidad total de premios")
    return data.reward_stock if data.reward_display == "quantity" else None


def normalize_slug(value: str, fallback: str = "") -> str:
    raw = (value or fallback).strip().lower()
    if "://" in raw:
        raw = urlparse(raw).path
    if "/b/" in raw:
        raw = raw.split("/b/", 1)[1]
    raw = raw.strip("/ ")
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    if len(raw) < 2 or len(raw) > 80:
        raise HTTPException(status_code=422, detail="La URL corta debe tener entre 2 y 80 caracteres. Ejemplo: mi-negocio")
    return raw


def normalize_username(value: str, fallback: str = "") -> str:
    raw = (value or fallback).strip().lower()
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-z0-9._-]+", "", raw)
    if len(raw) < 3 or len(raw) > 50:
        raise HTTPException(status_code=422, detail="El usuario debe tener entre 3 y 50 caracteres")
    return raw


def normalize_search(value: str) -> str:
    return unicodedata.normalize("NFKD", (value or "")).encode("ascii", "ignore").decode("ascii").lower().strip()


BACKUPS = ROOT / "backups"
BACKUP_EXTERNAL_DIRS = ("storage", "uploads", "media", "assets", "resources", "files")


def create_backup(label="manual"):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r"[^a-z]+", "", label.lower()) or "manual"
    target = BACKUPS / f"negrosky_{stamp}_{safe_label}.db"
    source = sqlite3.connect(database_path())
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    # La base conserva los registros y las imágenes que la plataforma guarda
    # dentro de SQLite. El ZIP agrega también todos los recursos externos que
    # realmente existan en la instalación.
    archive = BACKUPS / f"negrosky_{stamp}_{safe_label}.zip"
    external_files = []
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        bundle.write(target, arcname=f"database/{target.name}")
        # Estos campos permiten verificar que la copia no es solo un ZIP vacío
        # y que la restauración recibió exactamente sus recursos externos.
        manifest = {
            "format": "negrosky-loyalty-full-backup-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": f"database/{target.name}",
            "database_size": target.stat().st_size,
            "embedded_images": True,
            "external_directories": list(BACKUP_EXTERNAL_DIRS),
            "external_files": external_files,
        }
        for directory_name in BACKUP_EXTERNAL_DIRS:
            directory = ROOT / directory_name
            if not directory.is_dir():
                continue
            for item in directory.rglob("*"):
                if item.is_file():
                    relative = item.relative_to(directory).as_posix()
                    archive_name = f"files/{directory_name}/{relative}"
                    bundle.write(item, arcname=archive_name)
                    external_files.append({
                        "path": f"{directory_name}/{relative}",
                        "size": item.stat().st_size,
                    })
        # Escribir el manifiesto al final para incluir el inventario real.
        bundle.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return target


def _backup_kind(path: Path) -> str:
    if path.suffix.lower() == ".db":
        return "db"
    if path.suffix.lower() == ".zip":
        return "zip"
    return "unknown"


def _zip_database_path(bundle: zipfile.ZipFile) -> str | None:
    names = [name for name in bundle.namelist() if name.startswith("database/") and name.lower().endswith(".db")]
    if not names:
        names = [name for name in bundle.namelist() if name.lower().endswith(".db")]
    return names[0] if names else None


def _validate_database_file(path: Path):
    check = sqlite3.connect(path)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise HTTPException(status_code=409, detail="El respaldo está dañado")
    finally:
        check.close()


def _restore_backup_path(source: Path):
    kind = _backup_kind(source)
    if kind == "db":
        _validate_database_file(source)
        shutil.copy2(source, database_path())
        return
    if kind != "zip":
        raise HTTPException(status_code=422, detail="Solo se permiten copias .db o .zip")
    try:
        with zipfile.ZipFile(source) as bundle:
            try:
                manifest_name = next(
                    (
                        name for name in bundle.namelist()
                        if Path(name).name.lower() == "backup_manifest.json"
                    ),
                    None,
                )
                if not manifest_name:
                    raise KeyError("backup_manifest.json")
                manifest = json.loads(bundle.read(manifest_name).decode("utf-8-sig"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
                raise HTTPException(status_code=409, detail="El ZIP no contiene un manifiesto válido")
            backup_format = str(manifest.get("format", ""))
            if not backup_format.startswith("negrosky-loyalty-full-backup"):
                raise HTTPException(status_code=409, detail="Formato de respaldo no compatible")
            database_name = _zip_database_path(bundle)
            if not database_name:
                raise HTTPException(status_code=409, detail="El ZIP no contiene una base de datos")
            database_bytes = bundle.read(database_name)
            extracted = BACKUPS / ("restore_database_" + source.stem + ".db")
            extracted.write_bytes(database_bytes)
            try:
                _validate_database_file(extracted)
                shutil.copy2(extracted, database_path())
            finally:
                extracted.unlink(missing_ok=True)
            # Los archivos externos se restauran únicamente dentro de las
            # carpetas permitidas y con validación contra traversal.
            restored_files = 0
            for name in bundle.namelist():
                if not name.startswith("files/") or name.endswith("/"):
                    continue
                relative = Path(name.removeprefix("files/"))
                if not relative.parts or relative.parts[0] not in set(BACKUP_EXTERNAL_DIRS):
                    continue
                destination = (ROOT / relative).resolve()
                if ROOT.resolve() not in destination.parents:
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(bundle.read(name))
                restored_files += 1
            return {"restored_files": restored_files, "database": database_name}
    except zipfile.BadZipFile:
        raise HTTPException(status_code=409, detail="El archivo ZIP está dañado")


def audit(con, user, action, entity_type, entity_id=None, details=None):
    con.execute(
        """INSERT INTO audit_logs
        (tenant_id, branch_id, user_id, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user.get("tenant_id"), user.get("branch_id"), user["id"], action,
            entity_type, entity_id, json.dumps(details or {}, ensure_ascii=False),
        ),
    )


def bootstrap_admin():
    email = os.getenv("NEGROSKY_ADMIN_EMAIL", "admin@negrosky.local").lower()
    password = os.getenv("NEGROSKY_ADMIN_PASSWORD", "ChangeMe123!")
    with connection() as con:
        if not con.execute("SELECT 1 FROM users WHERE role='super_admin' LIMIT 1").fetchone():
            con.execute(
                """INSERT INTO users
                (name, username, email, password_hash, role) VALUES (?, 'admin', ?, ?, 'super_admin')""",
                ("Administrador General", email, hash_password(password)),
            )


@app.on_event("startup")
def startup():
    init_db()
    sync_module_defaults()
    bootstrap_admin()


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sesión requerida")
    try:
        payload = decode_token(authorization[7:])
        if payload.get("type") != "user":
            raise ValueError("Tipo de sesión inválido")
    except Exception:
        raise HTTPException(status_code=401, detail="Sesión inválida o vencida")
    if not payload.get("sid"):
        raise HTTPException(status_code=401, detail="Inicia sesión nuevamente para actualizar la seguridad")
    with connection() as con:
        session = con.execute(
            "SELECT * FROM user_sessions WHERE id=? AND user_id=? AND revoked_at IS NULL",
            (payload["sid"], payload["sub"]),
        ).fetchone()
        if not session or datetime.fromisoformat(session["expires_at"]) < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Sesión cerrada o vencida")
        user = con.execute(
            """SELECT id, tenant_id, branch_id, name, username, email, email_optional,
            role, status, force_password_change
            FROM users WHERE id = ?""", (payload["sub"],)
        ).fetchone()
        con.execute("UPDATE user_sessions SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?", (payload["sid"],))
    if not user or user["status"] != "active":
        raise HTTPException(status_code=401, detail="Usuario inactivo")
    result = row_dict(user)
    result["session_id"] = payload["sid"]
    if result.get("email_optional") and result.get("email", "").endswith("@no-email.negrosky.local"):
        result["email"] = None
    return result


def current_customer(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Identificación requerida")
    try:
        payload = decode_token(authorization[7:])
        if payload.get("type") != "customer":
            raise ValueError("Tipo de sesión inválido")
    except Exception:
        raise HTTPException(status_code=401, detail="Identificación inválida o vencida")
    with connection() as con:
        customer = con.execute("SELECT * FROM customers WHERE id=? AND tenant_id=?", (payload["sub"], payload["tenant_id"])).fetchone()
    if not customer or customer["status"] != "active":
        raise HTTPException(status_code=401, detail="Cliente inactivo")
    return row_dict(customer)


def require(*roles):
    def dependency(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="No tiene permiso")
        return user
    return dependency


WORKER_ACCESS_PERMISSIONS = {
    "validate_purchase": "Validar compras y fidelización",
    "validate_raffle": "Validar rifas y boletas",
    "validate_reward": "Entregar premios",
    "time_sales": "Venta por tiempo",
    "appointments": "Gestionar citas y reservas",
    "notifications": "Enviar notificaciones",
}

DEFAULT_WORKER_SCHEDULE = [
    {"weekday": day, "enabled": True, "opens_at": "00:00", "closes_at": "23:59"}
    for day in range(7)
]


def _worker_access(con, user_id):
    row = con.execute("SELECT permissions_json,schedule_json FROM worker_access WHERE user_id=?", (user_id,)).fetchone()
    permissions = {key: True for key in WORKER_ACCESS_PERMISSIONS}
    schedule = DEFAULT_WORKER_SCHEDULE
    if row:
        try:
            permissions.update({key: bool(value) for key, value in json.loads(row["permissions_json"] or "{}").items() if key in WORKER_ACCESS_PERMISSIONS})
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        try:
            loaded = json.loads(row["schedule_json"] or "[]")
            if isinstance(loaded, list) and loaded:
                schedule = loaded
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return permissions, schedule


def require_worker_access(con, user, permission):
    if user.get("role") != "worker":
        return
    permissions, schedule = _worker_access(con, user["id"])
    if not permissions.get(permission, False):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para realizar esta operación.")
    tenant = con.execute("SELECT timezone FROM tenants WHERE id=?", (user["tenant_id"],)).fetchone()
    try:
        zone = ZoneInfo(tenant["timezone"] if tenant and tenant["timezone"] else "America/Bogota")
    except ZoneInfoNotFoundError:
        zone = timezone(timedelta(hours=-5))
    now = datetime.now(zone)
    today = next((item for item in schedule if int(item.get("weekday", -1)) == now.weekday()), None)
    if not today or not today.get("enabled", False):
        raise HTTPException(status_code=403, detail="El trabajador no está dentro de su horario laboral.")
    try:
        current = now.hour * 60 + now.minute
        start = int(str(today.get("opens_at", "00:00"))[:2]) * 60 + int(str(today.get("opens_at", "00:00"))[3:5])
        end = int(str(today.get("closes_at", "23:59"))[:2]) * 60 + int(str(today.get("closes_at", "23:59"))[3:5])
    except (TypeError, ValueError, IndexError):
        raise HTTPException(status_code=403, detail="El horario laboral del trabajador no está configurado correctamente.")
    if current < start or current > end:
        raise HTTPException(status_code=403, detail="El trabajador no está dentro de su horario laboral.")


def tenant_scope(user, requested=None) -> int:
    if user["role"] == "super_admin":
        if requested is None:
            raise HTTPException(status_code=422, detail="tenant_id es obligatorio")
        return requested
    if requested is not None and requested != user["tenant_id"]:
        raise HTTPException(status_code=403, detail="Negocio fuera de su alcance")
    return user["tenant_id"]


MODULE_CATALOG = {
    "loyalty": {
        "label": "Fidelización",
        "description": "Tarjetas, compras, puntos y premios.",
    },
    "appointments": {
        "label": "Agenda de citas",
        "description": "Reservas, servicios y calendario.",
    },
    "time_sales": {
        "label": "Venta por tiempo",
        "description": "Servicios por minutos u horas.",
    },
    "notifications": {
        "label": "Notificaciones",
        "description": "Avisos internos y actualizaciones al cliente.",
    },
    "public_page": {
        "label": "Página pública",
        "description": "Página, QR y tarjeta pública del negocio.",
    },
    "raffles": {
        "label": "Rifas",
        "description": "Campañas de boletas y sorteos.",
    },
    "roulette": {
        "label": "Ruleta de suerte",
        "description": "Juego promocional configurable.",
    },
    "collaborations": {
        "label": "Colaboraciones",
        "description": "Alianzas y publicidad entre negocios.",
    },
}
MODULE_KEYS = set(MODULE_CATALOG)
DEFAULT_MODULES = {
    "loyalty": True,
    "appointments": False,
    "time_sales": False,
    "notifications": False,
    "public_page": True,
    "raffles": True,
    "roulette": True,
    "collaborations": False,
}


def initialize_tenant_modules(con, tenant_id: int):
    """Create explicit module flags for a new business without changing existing flags."""
    con.executemany(
        "INSERT OR IGNORE INTO feature_modules (tenant_id, branch_id, module_key, enabled) VALUES (?, NULL, ?, ?)",
        [(tenant_id, key, int(DEFAULT_MODULES.get(key, False))) for key in MODULE_KEYS],
    )


def sync_module_defaults():
    """Backfill the module catalog for businesses created by older builds."""
    with connection() as con:
        tenant_ids = [row[0] for row in con.execute("SELECT id FROM tenants").fetchall()]
        for tenant_id in tenant_ids:
            initialize_tenant_modules(con, tenant_id)
            con.execute("INSERT OR REPLACE INTO tenant_onboarding (tenant_id,setup_mode) VALUES (?,?)", (tenant_id, data.setup_mode))


def effective_modules(con, tenant_id: int, branch_id: int | None = None):
    return {key: module_enabled(con, tenant_id, key, branch_id) for key in MODULE_KEYS}
DEFAULT_HOURS = [
    {"weekday": day, "enabled": True, "opens_at": "00:00", "closes_at": "23:59"}
    for day in range(7)
]


def _hours_open(rows, now_local):
    if not rows:
        return True
    by_day = {row["weekday"]: row for row in rows}
    today = by_day.get(now_local.weekday())
    current = now_local.strftime("%H:%M")
    if today and today["enabled"]:
        opens, closes = today["opens_at"], today["closes_at"]
        if opens <= closes and opens <= current <= closes:
            return True
        if closes < opens and current >= opens:
            return True
    previous = by_day.get((now_local.weekday() - 1) % 7)
    if previous and previous["enabled"] and previous["closes_at"] < previous["opens_at"]:
        return current <= previous["closes_at"]
    return False


def service_status(con, tenant_id: int, branch_id: int | None = None):
    tenant = con.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    if not tenant or tenant["status"] != "active":
        return {"open": False, "reason": "inactive", "message": "Este negocio no se encuentra disponible."}
    try:
        now_local = datetime.now(ZoneInfo(tenant["timezone"]))
    except ZoneInfoNotFoundError:
        now_local = datetime.now(timezone(timedelta(hours=-5)))
    message = tenant["closed_message"]
    if tenant["manual_closed"]:
        return {"open": False, "reason": "manual", "message": message, "local_time": now_local.isoformat()}
    tenant_hours = con.execute(
        "SELECT weekday, enabled, opens_at, closes_at FROM business_hours WHERE tenant_id=? AND branch_id IS NULL",
        (tenant_id,),
    ).fetchall()
    tenant_open = _hours_open(tenant_hours, now_local)
    branch = None
    if branch_id is not None:
        branch = con.execute("SELECT * FROM branches WHERE id=? AND tenant_id=? AND status='active'", (branch_id, tenant_id)).fetchone()
        if not branch:
            return {"open": False, "reason": "branch_inactive", "message": "Esta sucursal no se encuentra disponible."}
        message = branch["closed_message"] or message
        if branch["manual_closed"]:
            return {"open": False, "reason": "branch_manual", "message": message, "local_time": now_local.isoformat()}
        if branch["schedule_mode"] == "custom":
            rows = con.execute(
                "SELECT weekday, enabled, opens_at, closes_at FROM business_hours WHERE tenant_id=? AND branch_id=?",
                (tenant_id, branch_id),
            ).fetchall()
            tenant_open = _hours_open(rows, now_local)
    return {
        "open": bool(tenant_open),
        "reason": "open" if tenant_open else "schedule",
        "message": "Servicio disponible." if tenant_open else message,
        "local_time": now_local.isoformat(),
        "schedule_mode": branch["schedule_mode"] if branch else "business",
    }


def require_service_open(con, tenant_id, branch_id=None):
    current = service_status(con, tenant_id, branch_id)
    if not current["open"]:
        raise HTTPException(status_code=409, detail=current["message"])
    return current


def module_enabled(con, tenant_id: int, module_key: str, branch_id: int | None = None) -> bool:
    enabled = DEFAULT_MODULES.get(module_key, False)
    tenant_value = con.execute(
        "SELECT enabled FROM feature_modules WHERE tenant_id=? AND branch_id IS NULL AND module_key=?",
        (tenant_id, module_key),
    ).fetchone()
    if tenant_value is not None:
        enabled = bool(tenant_value["enabled"])
        if not enabled:
            return False
    if branch_id is not None:
        branch_value = con.execute(
            "SELECT enabled FROM feature_modules WHERE tenant_id=? AND branch_id=? AND module_key=?",
            (tenant_id, branch_id, module_key),
        ).fetchone()
        if branch_value is not None:
            enabled = bool(branch_value["enabled"])
    return enabled


def require_module(con, tenant_id: int, module_key: str, branch_id: int | None = None):
    if not module_enabled(con, tenant_id, module_key, branch_id):
        labels = {"loyalty": "fidelización", "public_page": "página pública",
                  "raffles": "rifas", "roulette": "ruleta"}
        raise HTTPException(
            status_code=409,
            detail=f"El módulo de {labels.get(module_key, module_key)} está desactivado para este negocio o sucursal.",
        )


def require_user_module(con, user: dict, module_key: str, branch_id: int | None = None):
    """Enforce a tenant feature without revealing hidden modules to owners."""
    if user.get("role") == "super_admin":
        return
    if not module_enabled(con, user["tenant_id"], module_key, branch_id or user.get("branch_id")):
        raise HTTPException(status_code=404, detail="Recurso no encontrado")


def require_public_module(con, tenant_id: int, module_key: str, branch_id: int | None = None):
    """Keep disabled public features indistinguishable from a missing resource."""
    if not module_enabled(con, tenant_id, module_key, branch_id):
        raise HTTPException(status_code=404, detail="Recurso no encontrado")


def add_notification(con, tenant_id: int, branch_id: int | None, customer_id: int | None,
                     event_type: str, title: str, message: str, image_url: str | None = None):
    if not module_enabled(con, tenant_id, "notifications", branch_id):
        return None
    cur = con.execute(
        """INSERT INTO notifications
        (tenant_id,branch_id,customer_id,event_type,title,message,image_url)
        VALUES (?,?,?,?,?,?,?)""",
        (tenant_id, branch_id, customer_id, event_type, title, message, image_url),
    )
    return cur.lastrowid

def send_push_notification(con, customer_id: int, title: str, message: str, url: str = "/"):
    """Send a background push when the optional pywebpush dependency is installed."""
    try:
        from pywebpush import webpush
    except ImportError:
        return False
    key = con.execute("SELECT private_key_pem FROM push_keys WHERE id=1").fetchone()
    subscriptions = con.execute("SELECT id,endpoint,p256dh,auth FROM push_subscriptions WHERE customer_id=?", (customer_id,)).fetchall()
    if not key or not subscriptions:
        return False
    delivered = False
    for sub in subscriptions:
        try:
            webpush({"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}}, json.dumps({"title": title, "body": message, "url": url}), vapid_private_key=key["private_key_pem"], vapid_claims={"sub": "mailto:admin@negrosky.local"})
            delivered = True
        except Exception as exc:
            if getattr(exc, "response", None) is not None and getattr(exc.response, "status_code", 0) in (404, 410):
                con.execute("DELETE FROM push_subscriptions WHERE id=?", (sub["id"],))
    return delivered


def parse_appointment_time(value: str, timezone_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha u hora de la cita no válida")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = timezone(timedelta(hours=-5))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(timezone.utc)


def appointment_fits_hours(con, tenant_id: int, branch_id: int, starts_utc: datetime,
                           ends_utc: datetime) -> bool:
    tenant = con.execute("SELECT timezone FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    try:
        zone = ZoneInfo(tenant["timezone"])
    except ZoneInfoNotFoundError:
        zone = timezone(timedelta(hours=-5))
    branch = con.execute("SELECT schedule_mode FROM branches WHERE id=? AND tenant_id=?", (branch_id, tenant_id)).fetchone()
    if not branch:
        return False
    hours_branch = branch_id if branch["schedule_mode"] == "custom" else None
    rows = con.execute(
        "SELECT weekday,enabled,opens_at,closes_at FROM business_hours WHERE tenant_id=? AND branch_id IS ?",
        (tenant_id, hours_branch),
    ).fetchall()
    if not rows:
        return True
    start_local = starts_utc.astimezone(zone)
    end_local = (ends_utc - timedelta(minutes=1)).astimezone(zone)
    return _hours_open(rows, start_local) and _hours_open(rows, end_local)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB / "index.html")

@app.get("/manifest.webmanifest", include_in_schema=False)
def pwa_manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")

@app.get("/service-worker.js", include_in_schema=False)
def pwa_service_worker():
    return FileResponse(WEB / "service-worker.js", media_type="application/javascript")

@app.get("/api/public/{slug}/manifest.webmanifest", include_in_schema=False)
def customer_manifest(slug: str):
    with connection() as con:
        tenant = con.execute("SELECT id,name FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        brand = branding_payload(con, tenant["id"])
    name = brand.get("display_name") or tenant["name"]
    return JSONResponse({
        "name": f"Tarjeta digital · {name}", "short_name": name[:18],
        "description": f"Tarjeta de fidelización de {name}",
        "start_url": f"/b/{slug}", "scope": "/", "display": "standalone",
        "background_color": brand.get("background_color") or "#07070d",
        "theme_color": brand.get("primary_color") or "#7c3aed", "lang": "es-CO",
        "icons": [{"src":"/static/pwa-icon.svg","sizes":"any","type":"image/svg+xml","purpose":"any maskable"}],
    })


@app.get("/b/{slug}", include_in_schema=False)
def customer_page(slug: str):
    init_db()
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page")
    return FileResponse(WEB / "customer.html")

@app.get("/cliente", include_in_schema=False)
def customer_directory_page():
    return FileResponse(WEB / "portal.html")

@app.get("/api/public/businesses")
def public_business_directory():
    init_db()
    with connection() as con:
        tenants = con.execute("SELECT id,name,slug FROM tenants WHERE status='active' AND deleted_at IS NULL ORDER BY name COLLATE NOCASE").fetchall()
        result = []
        for tenant in tenants:
            if not module_enabled(con, tenant["id"], "public_page"):
                continue
            brand = branding_payload(con, tenant["id"])
            result.append({"name": brand.get("display_name") or tenant["name"], "slug": tenant["slug"], "logo_url": brand.get("logo_url"), "welcome_text": brand.get("welcome_text")})
    return result

@app.get("/poster/{slug}", include_in_schema=False)
def business_poster_page(slug: str):
    init_db()
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page")
    return FileResponse(WEB / "poster.html")

@app.get("/q/{public_key}", include_in_schema=False)
def permanent_business_qr(public_key: str):
    init_db()
    with connection() as con:
        tenant = con.execute("SELECT id,slug FROM tenants WHERE public_key=? AND status='active' AND deleted_at IS NULL", (public_key,)).fetchone()
    if not tenant:
        raise HTTPException(status_code=404, detail="Código del negocio no encontrado")
    with connection() as con:
        require_public_module(con, tenant["id"], "public_page")
    return RedirectResponse(url=f"/b/{tenant['slug']}", status_code=307)


@app.get("/worker", include_in_schema=False)
def worker_page():
    return FileResponse(WEB / "worker.html")


@app.get("/api/qr/{code}.png", include_in_schema=False)
def qr_image(code: str, request: Request):
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=404, detail="Código inválido")
    import qrcode
    target = worker_link(request, code)
    image = qrcode.make(target)
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-QR-Target": target},
    )

@app.get("/api/public/{slug}/qr.png", include_in_schema=False)
def public_business_qr(slug: str, request: Request):
    init_db()
    with connection() as con:
        tenant = con.execute("SELECT id,slug,public_key FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    with connection() as con:
        require_public_module(con, tenant["id"], "public_page")
    import qrcode
    host = request.url.hostname or "127.0.0.1"
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        try:
            candidates = socket.gethostbyname_ex(socket.gethostname())[2]
        except OSError:
            candidates = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("192.168.1.1", 80)); candidates.append(probe.getsockname()[0])
        except OSError:
            pass
        candidates = [ip for ip in candidates if usable_lan_address(ip)]
        if candidates: host = sorted(candidates, key=lambda ip: (not ip.startswith("192.168."), ip))[0]
    target = f"{request.url.scheme}://{host}:{request.url.port or 8030}/q/{tenant['public_key']}"
    output = io.BytesIO(); qrcode.make(target).save(output, format="PNG"); output.seek(0)
    return StreamingResponse(output, media_type="image/png", headers={"Cache-Control": "no-store", "X-QR-Target": target})


def worker_link(request: Request, code: str) -> str:
    """Use a reachable local address for a QR generated from a PC localhost tab."""
    host = request.url.hostname or "127.0.0.1"
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        try:
            candidates = socket.gethostbyname_ex(socket.gethostname())[2]
        except OSError:
            candidates = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("192.168.1.1", 80))
                candidates.append(probe.getsockname()[0])
        except OSError:
            pass
        candidates = [ip for ip in candidates if usable_lan_address(ip)]
        if candidates:
            host = sorted(candidates, key=lambda ip: (not ip.startswith("192.168."), ip))[0]
    return f"{request.url.scheme}://{host}:{request.url.port or 8030}/worker?code={code}"


def usable_lan_address(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
        return ip.version == 4 and ip.is_private and not ip.is_loopback and not str(ip).startswith(("169.254.", "192.168.56.", "172.17.", "172.18."))
    except ValueError:
        return False


@app.get("/api/health")
def health():
    return {"system": "NEGROSKY LOYALTY V3", "version": "3.0.55", "build": "055", "port": 8030, "stable_url": True, "status": "ok"}


@app.get("/api/system/urls")
def system_urls(request: Request, slug: str | None = None, user=Depends(current_user)):
    addresses = set()
    try:
        addresses.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    # Algunas instalaciones de Windows no publican la IP LAN mediante hostname.
    # Esta conexión UDP no envía datos; solo permite conocer la interfaz de salida.
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0.2)
        probe.connect(("8.8.8.8", 80))
        addresses.add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    request_host = request.url.hostname
    if request_host and request_host not in {"127.0.0.1", "localhost", "0.0.0.0"}:
        addresses.add(request_host)
    addresses = sorted(
        ip for ip in addresses
        if ip and not ip.startswith(("127.", "169.254.", "192.168.56.", "172.17.", "172.18.", "10.255.")) and ":" not in ip
    )
    with connection() as con:
        if user["role"] == "super_admin":
            tenant_rows = con.execute(
                "SELECT id,name,slug FROM tenants WHERE status='active' ORDER BY name"
            ).fetchall()
        else:
            tenant_rows = con.execute(
                "SELECT id,name,slug FROM tenants WHERE id=? AND status='active'", (user["tenant_id"],)
            ).fetchall()
        if slug:
            selected = next((row for row in tenant_rows if row["slug"] == slug), None)
        else:
            selected = tenant_rows[0] if tenant_rows else None
        slug = selected["slug"] if selected else "mi-negocio"
    scheme = request.url.scheme or "http"
    port = request.url.port or 8030
    def links(host):
        base = f"{scheme}://{host}:{port}"
        return {"admin": base, "worker": f"{base}/worker", "customer": f"{base}/b/{slug}"}
    current_base = str(request.base_url).rstrip("/")
    businesses = []
    for tenant in tenant_rows:
        businesses.append({
            "id": tenant["id"],
            "name": tenant["name"],
            "slug": tenant["slug"],
            "current_url": f"{current_base}/b/{tenant['slug']}",
            "current_worker_url": f"{current_base}/worker?business={tenant['slug']}",
            "pc_url": f"{scheme}://127.0.0.1:{port}/b/{tenant['slug']}",
            "pc_worker_url": f"{scheme}://127.0.0.1:{port}/worker?business={tenant['slug']}",
            "mobile": [
                {"ip": ip, "url": f"{scheme}://{ip}:{port}/b/{tenant['slug']}",
                 "worker_url": f"{scheme}://{ip}:{port}/worker?business={tenant['slug']}"} for ip in addresses
            ],
        })
    return {
        "current": {"admin": current_base, "worker": f"{current_base}/worker"},
        "pc": links("127.0.0.1"),
        "mobile": [{"ip": ip, **links(ip)} for ip in addresses],
        "businesses": businesses,
        "same_wifi_required": True,
        "slug": slug,
    }


@app.post("/api/auth/login")
def login(data: LoginInput, request: Request):
    identifier = (data.identifier or data.email or "").strip().lower()
    now = datetime.now(timezone.utc)
    login_error = None
    safe = None
    session_id = None
    with connection() as con:
        user = con.execute(
            "SELECT * FROM users WHERE lower(email)=? OR lower(username)=?", (identifier, identifier)
        ).fetchone()
        if user and user["locked_until"] and datetime.fromisoformat(user["locked_until"]) > now:
            login_error = HTTPException(status_code=423, detail="Cuenta bloqueada temporalmente. Intenta nuevamente en unos minutos.")
        elif not user or user["status"] != "active" or not verify_password(data.password, user["password_hash"]):
            if user:
                attempts = user["failed_attempts"] + 1
                locked = (now + timedelta(minutes=15)).isoformat() if attempts >= 5 else None
                con.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?", (0 if locked else attempts, locked, user["id"]))
            login_error = HTTPException(status_code=401, detail="Usuario, correo o contraseña incorrectos")
        else:
            session_id = secrets.token_urlsafe(24)
            expires = now + timedelta(days=365)
            con.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (user["id"],))
            con.execute(
                """INSERT INTO user_sessions (id,user_id,expires_at,user_agent,ip_address)
                VALUES (?,?,?,?,?)""",
                (session_id, user["id"], expires.isoformat(), request.headers.get("user-agent", "")[:300], request.client.host if request.client else None),
            )
            safe = row_dict(user)
    # Raise only after the transaction is committed so failed-attempt counters persist.
    if login_error:
        raise login_error
    safe.pop("password_hash", None)
    if safe.get("email_optional") and safe.get("email", "").endswith("@no-email.negrosky.local"):
        safe["email"] = None
    return {"access_token": create_token(safe, session_id), "token_type": "bearer", "user": safe}


@app.post("/api/auth/logout")
def logout(user=Depends(current_user)):
    with connection() as con:
        con.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE id=?", (user["session_id"],))
    return {"status": "closed"}


@app.post("/api/auth/change-password")
def change_password(data: PasswordChangeInput, user=Depends(current_user)):
    with connection() as con:
        stored = con.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
        if not verify_password(data.current_password, stored["password_hash"]):
            raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
        con.execute("UPDATE users SET password_hash=?, force_password_change=0, updated_at=CURRENT_TIMESTAMP WHERE id=?", (hash_password(data.new_password), user["id"]))
        con.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND id!=?", (user["id"], user["session_id"]))
        audit(con, user, "change_password", "user", user["id"])
    return {"status": "password_updated"}


@app.post("/api/auth/support-reset")
def support_reset(data: SupportResetInput):
    now = datetime.now(timezone.utc)
    identifier = data.identifier.strip().lower()
    with connection() as con:
        user = con.execute("SELECT * FROM users WHERE lower(email)=? OR lower(username)=?", (identifier, identifier)).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="Cuenta no encontrada")
        codes = con.execute("SELECT * FROM support_codes WHERE user_id=? AND used_at IS NULL ORDER BY id DESC", (user["id"],)).fetchall()
        valid = next((item for item in codes if datetime.fromisoformat(item["expires_at"]) >= now and verify_password(data.code, item["code_hash"])), None)
        if not valid:
            raise HTTPException(status_code=400, detail="Código temporal incorrecto o vencido")
        con.execute("UPDATE users SET password_hash=?, force_password_change=0, failed_attempts=0, locked_until=NULL WHERE id=?", (hash_password(data.new_password), user["id"]))
        con.execute("UPDATE support_codes SET used_at=? WHERE id=?", (now.isoformat(), valid["id"]))
        con.execute("UPDATE user_sessions SET revoked_at=? WHERE user_id=?", (now.isoformat(), user["id"]))
    return {"status": "password_reset", "message": "Contraseña actualizada. Ya puedes iniciar sesión."}


@app.get("/api/me")
def me(business: str | None = None, user=Depends(current_user)):
    with connection() as con:
        tenant = con.execute("SELECT name,slug FROM tenants WHERE id=?", (user.get("tenant_id"),)).fetchone() if user.get("tenant_id") else None
        if business and (not tenant or business.strip().lower() != (tenant["slug"] or "").strip().lower()):
            raise HTTPException(status_code=403, detail="Este enlace pertenece a otro negocio. Usa el enlace de tu negocio.")
        branch = con.execute("SELECT name FROM branches WHERE id=? AND tenant_id=?", (user.get("branch_id"), user.get("tenant_id"))).fetchone() if user.get("branch_id") else None
        branding = con.execute("SELECT display_name,primary_color,secondary_color,logo_mime FROM business_branding WHERE tenant_id=?", (user.get("tenant_id"),)).fetchone() if user.get("tenant_id") else None
    result = dict(user)
    result.update({"tenant_name": tenant["name"] if tenant else None, "tenant_slug": tenant["slug"] if tenant else None,
                   "branch_name": branch["name"] if branch else None,
                   "display_name": branding["display_name"] if branding and branding["display_name"] else (tenant["name"] if tenant else None),
                   "primary_color": branding["primary_color"] if branding else None,
                   "secondary_color": branding["secondary_color"] if branding else None,
                   "has_logo": bool(branding and branding["logo_mime"])})
    with connection() as con:
        if user["role"] == "super_admin":
            result["enabled_modules"] = sorted(MODULE_KEYS)
            result["module_catalog"] = [{"key": key, **details} for key, details in MODULE_CATALOG.items()]
        elif user.get("tenant_id"):
            result["enabled_modules"] = sorted(
                key for key, enabled in effective_modules(con, user["tenant_id"], user.get("branch_id")).items()
                if enabled
            )
        else:
            result["enabled_modules"] = []
    return result


@app.get("/api/me/sessions")
def my_sessions(user=Depends(current_user)):
    with connection() as con:
        rows = con.execute(
            """SELECT id,created_at,expires_at,last_seen_at,user_agent,ip_address,
            CASE WHEN id=? THEN 1 ELSE 0 END AS current
            FROM user_sessions WHERE user_id=? AND revoked_at IS NULL ORDER BY last_seen_at DESC""",
            (user["session_id"], user["id"]),
        ).fetchall()
    return [row_dict(row) for row in rows]


@app.delete("/api/me/sessions/{session_id}")
def close_session(session_id: str, user=Depends(current_user)):
    with connection() as con:
        found = con.execute("SELECT 1 FROM user_sessions WHERE id=? AND user_id=?", (session_id, user["id"])).fetchone()
        if not found:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        con.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))
    return {"status": "closed", "current": session_id == user["session_id"]}


@app.delete("/api/me/sessions")
def close_other_sessions(user=Depends(current_user)):
    with connection() as con:
        cur = con.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND id!=? AND revoked_at IS NULL", (user["id"], user["session_id"]))
    return {"status": "closed", "count": cur.rowcount}


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    with connection() as con:
        if user["role"] == "super_admin":
            businesses = con.execute("SELECT count(*) FROM tenants WHERE status='active'").fetchone()[0]
            branches = con.execute("SELECT count(*) FROM branches WHERE status='active'").fetchone()[0]
            users = con.execute("SELECT count(*) FROM users WHERE status='active'").fetchone()[0]
        else:
            businesses = 1
            branches = con.execute("SELECT count(*) FROM branches WHERE tenant_id=? AND status='active'", (user["tenant_id"],)).fetchone()[0]
            users = con.execute("SELECT count(*) FROM users WHERE tenant_id=? AND status='active'", (user["tenant_id"],)).fetchone()[0]
        if user["role"] == "super_admin":
            customers = con.execute("SELECT count(*) FROM customers WHERE status='active'").fetchone()[0]
        else:
            customers = con.execute("SELECT count(*) FROM customers WHERE tenant_id=? AND status='active'", (user["tenant_id"],)).fetchone()[0]
    return {"businesses": businesses, "branches": branches, "users": users, "customers": customers}


@app.get("/api/tenants")
def list_tenants(user=Depends(current_user)):
    with connection() as con:
        if user["role"] == "super_admin":
            rows = con.execute("SELECT * FROM tenants ORDER BY status='active' DESC, name COLLATE NOCASE").fetchall()
        else:
            rows = con.execute("SELECT * FROM tenants WHERE id=?", (user["tenant_id"],)).fetchall()
    return [row_dict(r) for r in rows]


def _platform_ad_dict(row):
    item = row_dict(row)
    try:
        item["target_tenants"] = json.loads(item.pop("target_tenants_json") or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        item["target_tenants"] = []
    item["all_tenants"] = not item["target_tenants"]
    item["is_active"] = bool(item.get("is_active"))
    return item


def _validate_platform_ad(data: PlatformAdInput):
    if not data.image_url.startswith("data:image/"):
        raise HTTPException(status_code=422, detail="Carga un flyer en formato PNG, JPG o WebP")
    if len(data.image_url) > 2_400_000:
        raise HTTPException(status_code=422, detail="La imagen es demasiado grande; usa un flyer más liviano")
    if data.starts_at and data.ends_at and data.ends_at < data.starts_at:
        raise HTTPException(status_code=422, detail="La fecha final debe ser posterior a la inicial")


@app.get("/api/platform-ads")
def list_platform_ads(user=Depends(require("super_admin"))):
    with connection() as con:
        rows = con.execute("SELECT * FROM platform_ads ORDER BY created_at DESC, id DESC").fetchall()
    return [_platform_ad_dict(row) for row in rows]


@app.post("/api/platform-ads", status_code=status.HTTP_201_CREATED)
def create_platform_ad(data: PlatformAdInput, user=Depends(require("super_admin"))):
    _validate_platform_ad(data)
    targets = sorted({int(item) for item in data.target_tenants if int(item) > 0})
    with connection() as con:
        if targets and len(con.execute("SELECT id FROM tenants WHERE id IN (%s)" % ",".join("?" * len(targets)), targets).fetchall()) != len(targets):
            raise HTTPException(status_code=422, detail="Uno de los negocios seleccionados no existe")
        cur = con.execute("""INSERT INTO platform_ads
            (title,message,image_url,target_tenants_json,starts_at,ends_at,ad_seconds,is_active,updated_at)
            VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""", (data.title.strip(), data.message or "", data.image_url, json.dumps(targets), data.starts_at, data.ends_at, data.ad_seconds, int(data.is_active)))
        row = con.execute("SELECT * FROM platform_ads WHERE id=?", (cur.lastrowid,)).fetchone()
    return _platform_ad_dict(row)


@app.put("/api/platform-ads/{ad_id}")
def update_platform_ad(ad_id: int, data: PlatformAdInput, user=Depends(require("super_admin"))):
    _validate_platform_ad(data)
    targets = sorted({int(item) for item in data.target_tenants if int(item) > 0})
    with connection() as con:
        if not con.execute("SELECT id FROM platform_ads WHERE id=?", (ad_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Publicidad no encontrada")
        if targets and len(con.execute("SELECT id FROM tenants WHERE id IN (%s)" % ",".join("?" * len(targets)), targets).fetchall()) != len(targets):
            raise HTTPException(status_code=422, detail="Uno de los negocios seleccionados no existe")
        con.execute("""UPDATE platform_ads SET title=?,message=?,image_url=?,target_tenants_json=?,starts_at=?,ends_at=?,ad_seconds=?,is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (data.title.strip(), data.message or "", data.image_url, json.dumps(targets), data.starts_at, data.ends_at, data.ad_seconds, int(data.is_active), ad_id))
        row = con.execute("SELECT * FROM platform_ads WHERE id=?", (ad_id,)).fetchone()
    return _platform_ad_dict(row)


@app.put("/api/platform-ads/{ad_id}/status")
def update_platform_ad_status(ad_id: int, active: dict, user=Depends(require("super_admin"))):
    with connection() as con:
        cur = con.execute("UPDATE platform_ads SET is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(bool(active.get("active"))), ad_id))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Publicidad no encontrada")
    return {"status": "active" if active.get("active") else "inactive"}


@app.delete("/api/platform-ads/{ad_id}")
def delete_platform_ad(ad_id: int, user=Depends(require("super_admin"))):
    with connection() as con:
        cur = con.execute("DELETE FROM platform_ads WHERE id=?", (ad_id,))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Publicidad no encontrada")
    return {"status": "deleted"}


@app.get("/api/business-ads")
def list_business_ads(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        rows = con.execute("SELECT * FROM business_ads WHERE tenant_id=? ORDER BY created_at DESC,id DESC", (scope,)).fetchall()
    return [{**row_dict(row), "is_active": bool(row["is_active"])} for row in rows]


@app.post("/api/business-ads", status_code=status.HTTP_201_CREATED)
def create_business_ad(data: BusinessAdInput, user=Depends(require("super_admin", "business_admin"))):
    _validate_platform_ad(PlatformAdInput(title=data.title, message=data.message, image_url=data.image_url, starts_at=data.starts_at, ends_at=data.ends_at, ad_seconds=data.ad_seconds, is_active=data.is_active))
    scope = tenant_scope(user, data.tenant_id)
    with connection() as con:
        cur = con.execute("INSERT INTO business_ads (tenant_id,title,message,image_url,starts_at,ends_at,ad_seconds,is_active,updated_at) VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)", (scope, data.title.strip(), data.message or "", data.image_url, data.starts_at, data.ends_at, data.ad_seconds, int(data.is_active)))
        row = con.execute("SELECT * FROM business_ads WHERE id=?", (cur.lastrowid,)).fetchone()
    return {**row_dict(row), "is_active": bool(row["is_active"])}


@app.put("/api/business-ads/{ad_id}")
def update_business_ad(ad_id: int, data: BusinessAdInput, user=Depends(require("super_admin", "business_admin"))):
    _validate_platform_ad(PlatformAdInput(title=data.title, message=data.message, image_url=data.image_url, starts_at=data.starts_at, ends_at=data.ends_at, ad_seconds=data.ad_seconds, is_active=data.is_active))
    with connection() as con:
        row = con.execute("SELECT * FROM business_ads WHERE id=?", (ad_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Publicidad no encontrada")
        scope = tenant_scope(user, data.tenant_id or row["tenant_id"])
        if row["tenant_id"] != scope:
            raise HTTPException(status_code=403, detail="No tiene permiso para esta publicidad")
        con.execute("UPDATE business_ads SET title=?,message=?,image_url=?,starts_at=?,ends_at=?,ad_seconds=?,is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (data.title.strip(), data.message or "", data.image_url, data.starts_at, data.ends_at, data.ad_seconds, int(data.is_active), ad_id))
        row = con.execute("SELECT * FROM business_ads WHERE id=?", (ad_id,)).fetchone()
    return {**row_dict(row), "is_active": bool(row["is_active"])}


@app.put("/api/business-ads/{ad_id}/status")
def update_business_ad_status(ad_id: int, active: dict, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        row = con.execute("SELECT tenant_id FROM business_ads WHERE id=?", (ad_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Publicidad no encontrada")
        tenant_scope(user, row["tenant_id"])
        con.execute("UPDATE business_ads SET is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(bool(active.get("active"))), ad_id))
    return {"status": "active" if active.get("active") else "inactive"}


@app.delete("/api/business-ads/{ad_id}")
def delete_business_ad(ad_id: int, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        row = con.execute("SELECT tenant_id FROM business_ads WHERE id=?", (ad_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Publicidad no encontrada")
        tenant_scope(user, row["tenant_id"])
        con.execute("DELETE FROM business_ads WHERE id=?", (ad_id,))
    return {"status": "deleted"}


@app.get("/api/onboarding")
def get_onboarding(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        con.execute("INSERT OR IGNORE INTO tenant_onboarding (tenant_id) VALUES (?)", (scope,))
        row = con.execute("SELECT tenant_id,completed,current_step,setup_mode,updated_at FROM tenant_onboarding WHERE tenant_id=?", (scope,)).fetchone()
    return {**row_dict(row), "completed": bool(row["completed"])}


@app.put("/api/onboarding")
def update_onboarding(data: dict, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, data.get("tenant_id"))
    step = max(0, min(20, int(data.get("current_step", 0) or 0)))
    completed = int(bool(data.get("completed", False)))
    with connection() as con:
        con.execute("INSERT INTO tenant_onboarding (tenant_id,completed,current_step,updated_at) VALUES (?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(tenant_id) DO UPDATE SET completed=excluded.completed,current_step=excluded.current_step,updated_at=CURRENT_TIMESTAMP", (scope, completed, step))
    return {"tenant_id": scope, "completed": bool(completed), "current_step": step}


@app.post("/api/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant(data: TenantInput, user=Depends(require("super_admin"))):
    slug = normalize_slug(data.slug, data.name)
    try:
        with connection() as con:
            cur = con.execute("INSERT INTO tenants (name, slug, public_key) VALUES (?, ?, ?)", (data.name.strip(), slug, secrets.token_urlsafe(12)))
            tenant_id = cur.lastrowid
            initialize_tenant_modules(con, tenant_id)
            audit(con, user, "create", "tenant", tenant_id, data.model_dump())
            tenant = con.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        return row_dict(tenant)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"La URL /b/{slug} ya pertenece a otro negocio. Escribe una diferente.")

@app.put("/api/tenants/{tenant_id}")
def update_tenant(tenant_id: int, data: TenantUpdate, user=Depends(require("super_admin", "business_admin"))):
    if user["role"] != "super_admin":
        tenant_scope(user, tenant_id)
    slug = normalize_slug(data.slug, data.name)
    try:
        with connection() as con:
            tenant = con.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
            if not tenant:
                raise HTTPException(status_code=404, detail="Negocio no encontrado")
            con.execute("UPDATE tenants SET name=?, slug=? WHERE id=?", (data.name.strip(), slug, tenant_id))
            audit(con, user, "update", "tenant", tenant_id, data.model_dump())
            updated = con.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        return row_dict(updated)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="La URL corta ya pertenece a otro negocio")


@app.delete("/api/tenants/{tenant_id}")
def trash_tenant(tenant_id: int, user=Depends(require("super_admin"))):
    backup = create_backup("tenant")
    with connection() as con:
        tenant = con.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        con.execute("UPDATE tenants SET status='trashed', deleted_at=CURRENT_TIMESTAMP WHERE id=?", (tenant_id,))
        con.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id IN (SELECT id FROM users WHERE tenant_id=?) AND revoked_at IS NULL", (tenant_id,))
        audit(con, user, "trash", "tenant", tenant_id, {"backup": backup.name})
    return {"status": "trashed", "data_preserved": True, "backup": backup.name}


@app.put("/api/tenants/{tenant_id}/restore")
def restore_tenant(tenant_id: int, user=Depends(require("super_admin"))):
    with connection() as con:
        if not con.execute("SELECT 1 FROM tenants WHERE id=? AND status='trashed'", (tenant_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Negocio no encontrado en la papelera")
        con.execute("UPDATE tenants SET status='active', deleted_at=NULL WHERE id=?", (tenant_id,))
        audit(con, user, "restore", "tenant", tenant_id)
    return {"status": "active", "data_preserved": True}


def branding_payload(con, tenant_id: int):
    tenant = con.execute("SELECT id,name,slug FROM tenants WHERE id=? AND deleted_at IS NULL", (tenant_id,)).fetchone()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    branding = con.execute("SELECT * FROM business_branding WHERE tenant_id=?", (tenant_id,)).fetchone()
    values = row_dict(branding) if branding else {}
    values.pop("logo_blob", None)
    values.pop("background_blob", None)
    hours = con.execute(
        "SELECT weekday,enabled,opens_at,closes_at FROM business_hours WHERE tenant_id=? AND branch_id IS NULL ORDER BY weekday",
        (tenant_id,),
    ).fetchall()
    public_hours = [row_dict(row) for row in hours] or [dict(row) for row in DEFAULT_HOURS]
    return {
        "tenant_id": tenant["id"], "slug": tenant["slug"],
        "enabled_modules": effective_modules(con, tenant_id),
        "theme_key": values.get("theme_key") or "custom",
        "display_name": values.get("display_name") or tenant["name"],
        "welcome_text": values.get("welcome_text") or "Bienvenido a nuestro club de beneficios",
        "primary_color": values.get("primary_color") or "#a970ff",
        "secondary_color": values.get("secondary_color") or "#7547d8",
        "button_color": values.get("button_color") or "#7c3aed",
        "background_style": values.get("background_style") or "dark",
        "background_color": values.get("background_color") or "#07070d",
        "background_same_frame": bool(values.get("background_same_frame", 1)),
        "background_fit_desktop": values.get("background_fit_desktop") or "cover",
        "background_x_desktop": values.get("background_x_desktop") if values.get("background_x_desktop") is not None else 50,
        "background_y_desktop": values.get("background_y_desktop") if values.get("background_y_desktop") is not None else 50,
        "background_fit_mobile": values.get("background_fit_mobile") or "cover",
        "background_x_mobile": values.get("background_x_mobile") if values.get("background_x_mobile") is not None else 50,
        "background_y_mobile": values.get("background_y_mobile") if values.get("background_y_mobile") is not None else 50,
        "background_image_opacity": values.get("background_image_opacity") if values.get("background_image_opacity") is not None else 100,
        "background_overlay_opacity": values.get("background_overlay_opacity") if values.get("background_overlay_opacity") is not None else 35,
        "card_style": values.get("card_style") or "soft",
        "card_shape": values.get("card_shape") or "rounded",
        "card_opacity": values.get("card_opacity") if values.get("card_opacity") is not None else 94,
        "logo_shape": values.get("logo_shape") or "rounded",
        "logo_fit": values.get("logo_fit") or "contain",
        "logo_size": values.get("logo_size") if values.get("logo_size") is not None else 64,
        "logo_opacity": values.get("logo_opacity") if values.get("logo_opacity") is not None else 100,
        "logo_background_color": values.get("logo_background_color") or "#ffffff",
        "font_family": values.get("font_family") or "modern",
        "font_scale": values.get("font_scale") if values.get("font_scale") is not None else 100,
        "text_color": values.get("text_color") or "#f7f5ff",
        "button_shape": values.get("button_shape") or "rounded",
        "button_label": values.get("button_label") or "Registrar mi compra",
        "stamp_shape": values.get("stamp_shape") or "circle",
        "stamp_done_color": values.get("stamp_done_color") or values.get("secondary_color") or "#7547d8",
        "stamp_pending_color": values.get("stamp_pending_color") or "#252334",
        "progress_start_color": values.get("progress_start_color") or values.get("primary_color") or "#a970ff",
        "progress_end_color": values.get("progress_end_color") or values.get("secondary_color") or "#7547d8",
        "progress_style": values.get("progress_style") or "normal",
        "show_profile": bool(values.get("show_profile", 1)),
        "show_rewards": bool(values.get("show_rewards", 1)),
        "show_appointments": bool(values.get("show_appointments", 1)),
        "show_contact": bool(values.get("show_contact", 1)),
        "show_business_hours": bool(values.get("show_business_hours", 1)),
        "show_campaign_title": bool(values.get("show_campaign_title", 1)),
        "show_campaign_stamps": bool(values.get("show_campaign_stamps", 1)),
        "show_campaign_progress": bool(values.get("show_campaign_progress", 1)),
        "show_campaign_reward": bool(values.get("show_campaign_reward", 1)),
        "show_campaign_button": bool(values.get("show_campaign_button", 1)),
        "contact_phone": values.get("contact_phone"),
        "whatsapp_number": values.get("whatsapp_number"),
        "address": values.get("address"),
        "instagram_url": values.get("instagram_url"),
        "facebook_url": values.get("facebook_url"),
        "tiktok_url": values.get("tiktok_url"),
        "website_url": values.get("website_url"),
        "maps_url": values.get("maps_url"),
        "social_display_mode": values.get("social_display_mode") or "both",
        "social_size": values.get("social_size") or "medium",
        "social_layout": values.get("social_layout") or "inline",
        "social_position": values.get("social_position") or "bottom-right",
        "show_social_mobile": bool(values.get("show_social_mobile", 1)),
        "show_social_desktop": bool(values.get("show_social_desktop", 1)),
        "module_order_mobile": values.get("module_order_mobile") or "contact,profile,campaigns,rewards,appointments",
        "module_order_desktop": values.get("module_order_desktop") or "contact,profile,campaigns,rewards,appointments",
        "module_widths_mobile": values.get("module_widths_mobile") or "contact:100,profile:100,campaigns:100,rewards:100,appointments:100",
        "module_widths_desktop": values.get("module_widths_desktop") or "contact:100,profile:50,campaigns:50,rewards:50,appointments:50",
        "business_hours": public_hours,
        "logo_url": f"/api/public/branding/{tenant_id}/logo" if values.get("logo_mime") else None,
        "background_url": f"/api/public/branding/{tenant_id}/background" if values.get("background_mime") else None,
        "updated_at": values.get("updated_at"),
    }


@app.get("/api/branding")
def get_branding(tenant_id: int | None = None,
                 user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    # Autorrepara instalaciones actualizadas que aún no ejecutaron la migración visual.
    init_db()
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "public_page")
        return branding_payload(con, scope)


@app.put("/api/branding")
def update_branding(data: BrandingInput, tenant_id: int | None = None,
                    user=Depends(require("super_admin", "business_admin"))):
    init_db()
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "public_page")
        if not con.execute("SELECT 1 FROM tenants WHERE id=? AND deleted_at IS NULL", (scope,)).fetchone():
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        con.execute("""INSERT INTO business_branding
            (tenant_id,theme_key,display_name,welcome_text,primary_color,secondary_color,button_color,
             background_style,background_color,background_same_frame,background_fit_desktop,
             background_x_desktop,background_y_desktop,background_fit_mobile,background_x_mobile,
             background_y_mobile,background_image_opacity,background_overlay_opacity,
             card_style,card_shape,card_opacity,logo_shape,logo_fit,logo_size,logo_opacity,
             logo_background_color,font_family,
             font_scale,text_color,button_shape,button_label,stamp_shape,stamp_done_color,
             stamp_pending_color,progress_start_color,progress_end_color,progress_style,
             show_profile,show_rewards,show_appointments,show_contact,show_business_hours,
             show_campaign_title,show_campaign_stamps,show_campaign_progress,show_campaign_reward,show_campaign_button,
             contact_phone,whatsapp_number,address,instagram_url,facebook_url,tiktok_url,website_url,maps_url,
             social_display_mode,social_size,social_layout,social_position,show_social_mobile,show_social_desktop,
             module_order_mobile,module_order_desktop,module_widths_mobile,module_widths_desktop,updated_at)
            
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(tenant_id) DO UPDATE SET
            theme_key=excluded.theme_key,display_name=excluded.display_name,welcome_text=excluded.welcome_text,
            primary_color=excluded.primary_color,secondary_color=excluded.secondary_color,
            button_color=excluded.button_color,background_style=excluded.background_style,
            background_color=excluded.background_color,background_same_frame=excluded.background_same_frame,
            background_fit_desktop=excluded.background_fit_desktop,
            background_x_desktop=excluded.background_x_desktop,background_y_desktop=excluded.background_y_desktop,
            background_fit_mobile=excluded.background_fit_mobile,
            background_x_mobile=excluded.background_x_mobile,background_y_mobile=excluded.background_y_mobile,
            background_image_opacity=excluded.background_image_opacity,
            background_overlay_opacity=excluded.background_overlay_opacity,
            card_style=excluded.card_style,
            card_shape=excluded.card_shape,card_opacity=excluded.card_opacity,
            logo_shape=excluded.logo_shape,logo_fit=excluded.logo_fit,logo_size=excluded.logo_size,
            logo_opacity=excluded.logo_opacity,logo_background_color=excluded.logo_background_color,
            font_family=excluded.font_family,font_scale=excluded.font_scale,text_color=excluded.text_color,
            button_shape=excluded.button_shape,button_label=excluded.button_label,
            stamp_shape=excluded.stamp_shape,stamp_done_color=excluded.stamp_done_color,
            stamp_pending_color=excluded.stamp_pending_color,show_profile=excluded.show_profile,
            progress_start_color=excluded.progress_start_color,progress_end_color=excluded.progress_end_color,
            progress_style=excluded.progress_style,
            show_rewards=excluded.show_rewards,show_appointments=excluded.show_appointments,
            show_contact=excluded.show_contact,show_business_hours=excluded.show_business_hours,
            show_campaign_title=excluded.show_campaign_title,show_campaign_stamps=excluded.show_campaign_stamps,
            show_campaign_progress=excluded.show_campaign_progress,show_campaign_reward=excluded.show_campaign_reward,
            show_campaign_button=excluded.show_campaign_button,
            contact_phone=excluded.contact_phone,whatsapp_number=excluded.whatsapp_number,address=excluded.address,
            instagram_url=excluded.instagram_url,facebook_url=excluded.facebook_url,tiktok_url=excluded.tiktok_url,
            website_url=excluded.website_url,maps_url=excluded.maps_url,
            social_display_mode=excluded.social_display_mode,social_size=excluded.social_size,
            social_layout=excluded.social_layout,social_position=excluded.social_position,
            show_social_mobile=excluded.show_social_mobile,show_social_desktop=excluded.show_social_desktop,
            module_order_mobile=excluded.module_order_mobile,module_order_desktop=excluded.module_order_desktop,
            module_widths_mobile=excluded.module_widths_mobile,module_widths_desktop=excluded.module_widths_desktop,
            updated_at=CURRENT_TIMESTAMP""",
            (scope, data.theme_key, data.display_name.strip() if data.display_name else None, data.welcome_text.strip(),
             data.primary_color.lower(), data.secondary_color.lower(), data.button_color.lower(),
             data.background_style, data.background_color.lower(), int(data.background_same_frame),
             data.background_fit_desktop, data.background_x_desktop, data.background_y_desktop,
             data.background_fit_mobile, data.background_x_mobile, data.background_y_mobile,
             data.background_image_opacity, data.background_overlay_opacity,
             data.card_style, data.card_shape, data.card_opacity, data.logo_shape, data.logo_fit,
             data.logo_size, data.logo_opacity, data.logo_background_color.lower(),
             data.font_family, data.font_scale, data.text_color.lower(), data.button_shape,
             data.button_label.strip(), data.stamp_shape, data.stamp_done_color.lower(),
             data.stamp_pending_color.lower(), data.progress_start_color.lower(),
             data.progress_end_color.lower(), data.progress_style, int(data.show_profile), int(data.show_rewards),
             int(data.show_appointments), int(data.show_contact), int(data.show_business_hours),
             int(data.show_campaign_title), int(data.show_campaign_stamps), int(data.show_campaign_progress),
             int(data.show_campaign_reward), int(data.show_campaign_button),
             data.contact_phone, data.whatsapp_number, data.address, data.instagram_url, data.facebook_url,
             data.tiktok_url, data.website_url, data.maps_url, data.social_display_mode, data.social_size,
             data.social_layout, data.social_position, int(data.show_social_mobile), int(data.show_social_desktop),
             data.module_order_mobile, data.module_order_desktop, data.module_widths_mobile, data.module_widths_desktop))
        con.execute("UPDATE business_branding SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE tenant_id=?", (scope,))
        audit(con, user, "update", "business_branding", scope,
              {"background_style": data.background_style, "card_style": data.card_style})
        return branding_payload(con, scope)


@app.post("/api/branding/logo")
def update_branding_logo(data: BrandingLogoInput,
                         user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", data.data_url)
    if not match:
        raise HTTPException(status_code=422, detail="Usa una imagen PNG, JPG o WebP")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="La imagen no es válida")
    if not content or len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El logo debe pesar máximo 2 MB")
    mime = match.group(1)
    valid = ((mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or
             (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or
             (mime == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP"))
    if not valid:
        raise HTTPException(status_code=422, detail="El contenido de la imagen no coincide con su formato")
    with connection() as con:
        require_user_module(con, user, "public_page")
        if not con.execute("SELECT 1 FROM tenants WHERE id=? AND deleted_at IS NULL", (scope,)).fetchone():
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        con.execute("""INSERT INTO business_branding (tenant_id,logo_mime,logo_blob)
            VALUES (?,?,?) ON CONFLICT(tenant_id) DO UPDATE SET
            logo_mime=excluded.logo_mime,logo_blob=excluded.logo_blob,updated_at=CURRENT_TIMESTAMP""",
            (scope, mime, content))
        con.execute("UPDATE business_branding SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE tenant_id=?", (scope,))
        audit(con, user, "update_logo", "business_branding", scope, {"mime": mime, "size": len(content)})
    return {"status": "saved", "logo_url": f"/api/public/branding/{scope}/logo"}


@app.delete("/api/branding/logo")
def delete_branding_logo(tenant_id: int | None = None,
                         user=Depends(require("super_admin", "business_admin"))):
    init_db()
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "public_page")
        con.execute("UPDATE business_branding SET logo_mime=NULL,logo_blob=NULL,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=?", (scope,))
        con.execute("UPDATE business_branding SET updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE tenant_id=?", (scope,))
        audit(con, user, "delete_logo", "business_branding", scope)
    return {"status": "deleted"}


@app.get("/api/public/{slug}/branding")
def public_branding(slug: str):
    init_db()
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page")
        return branding_payload(con, tenant["id"])


@app.get("/api/public/branding/{tenant_id}/logo", include_in_schema=False)
def public_branding_logo(tenant_id: int):
    init_db()
    with connection() as con:
        require_public_module(con, tenant_id, "public_page")
        row = con.execute("""SELECT b.logo_mime,b.logo_blob FROM business_branding b
            JOIN tenants t ON t.id=b.tenant_id
            WHERE b.tenant_id=? AND t.status='active' AND t.deleted_at IS NULL""", (tenant_id,)).fetchone()
    if not row or not row["logo_blob"]:
        raise HTTPException(status_code=404, detail="Logo no encontrado")
    return StreamingResponse(io.BytesIO(row["logo_blob"]), media_type=row["logo_mime"],
                             headers={"Cache-Control": "public, max-age=300"})


@app.post("/api/branding/background")
def update_branding_background(data: BrandingBackgroundInput,
                               user=Depends(require("super_admin", "business_admin"))):
    init_db()
    scope = tenant_scope(user, data.tenant_id)
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", data.data_url)
    if not match:
        raise HTTPException(status_code=422, detail="Usa una imagen PNG, JPG o WebP")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="La imagen de fondo no es válida")
    if not content or len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El fondo debe pesar máximo 5 MB")
    mime = match.group(1)
    valid = ((mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or
             (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or
             (mime == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP"))
    if not valid:
        raise HTTPException(status_code=422, detail="El contenido del fondo no coincide con su formato")
    with connection() as con:
        require_user_module(con, user, "public_page")
        con.execute("""INSERT INTO business_branding (tenant_id,background_mime,background_blob)
            VALUES (?,?,?) ON CONFLICT(tenant_id) DO UPDATE SET
            background_mime=excluded.background_mime,background_blob=excluded.background_blob,
            updated_at=strftime('%Y-%m-%d %H:%M:%f','now')""", (scope, mime, content))
        audit(con, user, "update_background", "business_branding", scope, {"mime": mime, "size": len(content)})
    return {"status": "saved", "background_url": f"/api/public/branding/{scope}/background"}


@app.delete("/api/branding/background")
def delete_branding_background(tenant_id: int | None = None,
                               user=Depends(require("super_admin", "business_admin"))):
    init_db()
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "public_page")
        con.execute("""UPDATE business_branding SET background_mime=NULL,background_blob=NULL,
            updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE tenant_id=?""", (scope,))
        audit(con, user, "delete_background", "business_branding", scope)
    return {"status": "deleted"}


@app.get("/api/public/branding/{tenant_id}/background", include_in_schema=False)
def public_branding_background(tenant_id: int):
    init_db()
    with connection() as con:
        require_public_module(con, tenant_id, "public_page")
        row = con.execute("""SELECT b.background_mime,b.background_blob FROM business_branding b
            JOIN tenants t ON t.id=b.tenant_id WHERE b.tenant_id=? AND t.status='active'
            AND t.deleted_at IS NULL""", (tenant_id,)).fetchone()
    if not row or not row["background_blob"]:
        raise HTTPException(status_code=404, detail="Fondo no encontrado")
    return StreamingResponse(io.BytesIO(row["background_blob"]), media_type=row["background_mime"],
                             headers={"Cache-Control": "public, max-age=300"})


@app.delete("/api/branding/reset")
def reset_branding(tenant_id: int | None = None,
                   user=Depends(require("super_admin", "business_admin"))):
    init_db()
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "public_page")
        con.execute("DELETE FROM business_branding WHERE tenant_id=?", (scope,))
        audit(con, user, "reset", "business_branding", scope)
    return {"status": "reset"}


@app.get("/api/branches")
def list_branches(tenant_id: int | None = None, user=Depends(current_user)):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        rows = con.execute("SELECT * FROM branches WHERE tenant_id=? ORDER BY status='active' DESC, name COLLATE NOCASE", (scope,)).fetchall()
    return [row_dict(r) for r in rows]


@app.post("/api/branches", status_code=status.HTTP_201_CREATED)
def create_branch(data: BranchInput, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    try:
        with connection() as con:
            if not con.execute("SELECT 1 FROM tenants WHERE id=?", (scope,)).fetchone():
                raise HTTPException(status_code=404, detail="Negocio no encontrado")
            cur = con.execute(
                """INSERT INTO branches (tenant_id, name, city, address, phone)
                VALUES (?, ?, ?, ?, ?)""",
                (scope, data.name.strip(), data.city, data.address, data.phone),
            )
            branch_id = cur.lastrowid
            audit(con, user, "create", "branch", branch_id, data.model_dump())
            branch = con.execute("SELECT * FROM branches WHERE id=?", (branch_id,)).fetchone()
        return row_dict(branch)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="La sucursal ya existe")


@app.delete("/api/branches/{branch_id}")
def trash_branch(branch_id: int, user=Depends(require("super_admin", "business_admin"))):
    backup = create_backup("branch")
    with connection() as con:
        branch = con.execute("SELECT * FROM branches WHERE id=?", (branch_id,)).fetchone()
        if not branch:
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")
        tenant_scope(user, branch["tenant_id"])
        con.execute("UPDATE branches SET status='trashed', deleted_at=CURRENT_TIMESTAMP WHERE id=?", (branch_id,))
        con.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id IN (SELECT id FROM users WHERE branch_id=?) AND revoked_at IS NULL", (branch_id,))
        audit(con, user, "trash", "branch", branch_id, {"backup": backup.name})
    return {"status": "trashed", "data_preserved": True, "backup": backup.name}


@app.put("/api/branches/{branch_id}/restore")
def restore_branch(branch_id: int, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        branch = con.execute("SELECT * FROM branches WHERE id=?", (branch_id,)).fetchone()
        if not branch or branch["status"] != "trashed":
            raise HTTPException(status_code=404, detail="Sucursal no encontrada en la papelera")
        tenant_scope(user, branch["tenant_id"])
        con.execute("UPDATE branches SET status='active', deleted_at=NULL WHERE id=?", (branch_id,))
        audit(con, user, "restore", "branch", branch_id)
    return {"status": "active", "data_preserved": True}


def _settings_payload(con, tenant_id, branch_id=None, include_modules=False):
    tenant = con.execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    if not tenant:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    branch = None
    if branch_id is not None:
        branch = con.execute("SELECT * FROM branches WHERE id=? AND tenant_id=?", (branch_id, tenant_id)).fetchone()
        if not branch:
            raise HTTPException(status_code=404, detail="Sucursal no encontrada")
    hours_branch_id = None if branch and branch["schedule_mode"] == "inherit" else branch_id
    rows = con.execute(
        "SELECT weekday, enabled, opens_at, closes_at FROM business_hours WHERE tenant_id=? AND branch_id IS ? ORDER BY weekday",
        (tenant_id, hours_branch_id),
    ).fetchall()
    hours = [row_dict(row) for row in rows] or [dict(row) for row in DEFAULT_HOURS]
    payload = {
        "tenant_id": tenant_id,
        "branch_id": branch_id,
        "manual_closed": bool(branch["manual_closed"] if branch else tenant["manual_closed"]),
        "closed_message": (branch["closed_message"] if branch and branch["closed_message"] else tenant["closed_message"]),
        "timezone": tenant["timezone"],
        "schedule_mode": branch["schedule_mode"] if branch else "custom",
        "hours": hours,
        "current_status": service_status(con, tenant_id, branch_id),
    }
    # Module names and states are an administrator-only control surface.
    # Business owners receive schedules, but never the hidden module catalog.
    if include_modules:
        payload["modules"] = effective_modules(con, tenant_id, branch_id)
    return payload


@app.get("/api/service-settings")
def get_service_settings(tenant_id: int | None = None, branch_id: int | None = None,
                         user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        return _settings_payload(con, scope, branch_id, include_modules=user["role"] == "super_admin")


@app.get("/api/module-catalog")
def module_catalog(user=Depends(require("super_admin"))):
    """Return the complete private catalog only to the platform administrator."""
    return [{"key": key, **details} for key, details in MODULE_CATALOG.items()]


@app.get("/api/tenant-modules")
def get_tenant_modules(tenant_id: int, branch_id: int | None = None,
                       user=Depends(require("super_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE id=?", (scope,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        if branch_id is not None:
            branch = con.execute("SELECT id FROM branches WHERE id=? AND tenant_id=?", (branch_id, scope)).fetchone()
            if not branch:
                raise HTTPException(status_code=404, detail="Sucursal no encontrada")
        return {"tenant_id": scope, "branch_id": branch_id,
                "modules": effective_modules(con, scope, branch_id)}


@app.put("/api/tenant-modules")
def update_tenant_modules(data: ModuleSettingsInput, user=Depends(require("super_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    unknown = sorted(set(data.modules) - MODULE_KEYS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Módulo no reconocido: {', '.join(unknown)}")
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE id=?", (scope,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        # Older databases may not yet have rows for newly added modules.
        # Create those rows before reading and saving the complete state.
        initialize_tenant_modules(con, scope)
        if data.branch_id is not None:
            branch = con.execute("SELECT id FROM branches WHERE id=? AND tenant_id=?", (data.branch_id, scope)).fetchone()
            if not branch:
                raise HTTPException(status_code=404, detail="Sucursal no encontrada")
        before = effective_modules(con, scope, data.branch_id)
        # A missing value keeps the current effective state, preventing an
        # incomplete browser request from silently disabling a module.
        next_values = {key: bool(data.modules.get(key, before[key])) for key in MODULE_KEYS}
        con.execute(
            "DELETE FROM feature_modules WHERE tenant_id=? AND branch_id IS ?",
            (scope, data.branch_id),
        )
        con.executemany(
            "INSERT INTO feature_modules (tenant_id, branch_id, module_key, enabled) VALUES (?, ?, ?, ?)",
            [(scope, data.branch_id, key, int(value)) for key, value in next_values.items()],
        )
        audit(con, user, "update", "tenant_modules", data.branch_id or scope,
              {"tenant_id": scope, "branch_id": data.branch_id,
               "changed": {key: next_values[key] for key in MODULE_KEYS if before[key] != next_values[key]}})
        return {"tenant_id": scope, "branch_id": data.branch_id, "modules": next_values}


@app.put("/api/service-settings")
def update_service_settings(data: ServiceSettingsInput, tenant_id: int | None = None,
                            branch_id: int | None = None,
                            user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    if {item.weekday for item in data.hours} != set(range(7)):
        raise HTTPException(status_code=422, detail="Debes configurar los siete días de la semana")
    # Only the platform administrator can change feature availability.
    # Business owners may still manage hours and closure messages.
    if user["role"] == "super_admin":
        legacy = {"campaigns":"loyalty", "rewards":"loyalty", "contact":"public_page", "profile":"public_page"}
        normalized_modules = {legacy.get(key,key): value for key,value in data.modules.items() if key in MODULE_KEYS or key in legacy}
        unknown = sorted(set(data.modules) - MODULE_KEYS - set(legacy))
        if unknown:
            raise HTTPException(status_code=422, detail=f"Módulo no reconocido: {', '.join(unknown)}")
        data.modules = normalized_modules
    try:
        ZoneInfo(data.timezone)
    except ZoneInfoNotFoundError:
        if data.timezone != "America/Bogota":
            raise HTTPException(status_code=422, detail="Zona horaria no válida. Para Colombia usa America/Bogota")
    with connection() as con:
        if branch_id is None:
            con.execute(
                "UPDATE tenants SET manual_closed=?, closed_message=?, timezone=? WHERE id=?",
                (int(data.manual_closed), data.closed_message.strip(), data.timezone, scope),
            )
        else:
            branch = con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=?", (branch_id, scope)).fetchone()
            if not branch:
                raise HTTPException(status_code=404, detail="Sucursal no encontrada")
            con.execute(
                "UPDATE branches SET manual_closed=?, closed_message=?, schedule_mode=? WHERE id=?",
                (int(data.manual_closed), data.closed_message.strip(), data.schedule_mode, branch_id),
            )
        con.execute("DELETE FROM business_hours WHERE tenant_id=? AND branch_id IS ?", (scope, branch_id))
        con.executemany(
            "INSERT INTO business_hours (tenant_id, branch_id, weekday, enabled, opens_at, closes_at) VALUES (?, ?, ?, ?, ?, ?)",
            [(scope, branch_id, item.weekday, int(item.enabled), item.opens_at, item.closes_at) for item in data.hours],
        )
        if user["role"] == "super_admin":
            current = effective_modules(con, scope, branch_id)
            values = {key: bool(data.modules.get(key, current[key])) for key in MODULE_KEYS}
            con.execute("DELETE FROM feature_modules WHERE tenant_id=? AND branch_id IS ?", (scope, branch_id))
            con.executemany(
                "INSERT INTO feature_modules (tenant_id, branch_id, module_key, enabled) VALUES (?, ?, ?, ?)",
                [(scope, branch_id, key, int(value)) for key, value in values.items()],
            )
        audit(con, user, "update", "service_settings", branch_id or scope, {"branch_id": branch_id})
        return _settings_payload(con, scope, branch_id, include_modules=user["role"] == "super_admin")


@app.post("/api/service-settings/copy")
def copy_service_settings(data: CopyServiceSettingsInput,
                          user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    with connection() as con:
        source = _settings_payload(con, scope, data.source_branch_id, include_modules=user["role"] == "super_admin")
        targets = con.execute(
            f"SELECT id FROM branches WHERE tenant_id=? AND id IN ({','.join('?' for _ in data.target_branch_ids)})",
            (scope, *data.target_branch_ids),
        ).fetchall()
        if len(targets) != len(set(data.target_branch_ids)):
            raise HTTPException(status_code=422, detail="Una o más sucursales de destino no son válidas")
        for target in targets:
            target_id = target["id"]
            con.execute(
                "UPDATE branches SET schedule_mode='custom', closed_message=? WHERE id=?",
                (source["closed_message"], target_id),
            )
            con.execute("DELETE FROM business_hours WHERE tenant_id=? AND branch_id=?", (scope, target_id))
            con.executemany(
                "INSERT INTO business_hours (tenant_id, branch_id, weekday, enabled, opens_at, closes_at) VALUES (?, ?, ?, ?, ?, ?)",
                [(scope, target_id, item["weekday"], int(item["enabled"]), item["opens_at"], item["closes_at"]) for item in source["hours"]],
            )
            if user["role"] == "super_admin":
                con.execute("DELETE FROM feature_modules WHERE tenant_id=? AND branch_id=?", (scope, target_id))
                con.executemany(
                    "INSERT INTO feature_modules (tenant_id, branch_id, module_key, enabled) VALUES (?, ?, ?, ?)",
                    [(scope, target_id, key, int(value)) for key, value in source["modules"].items()],
                )
        audit(con, user, "copy", "service_settings", data.source_branch_id or scope,
              {"targets": data.target_branch_ids})
    return {"status": "copied", "branches_updated": len(targets), "manual_closure_copied": False}


@app.get("/api/users")
def list_users(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    if user["role"] == "super_admin" and tenant_id is None:
        query, params = "SELECT id, tenant_id, branch_id, name, username, CASE WHEN email_optional=1 THEN NULL ELSE email END AS email, email_optional, role, status, force_password_change, locked_until, created_at FROM users ORDER BY id DESC", ()
    else:
        scope = tenant_scope(user, tenant_id)
        query = "SELECT id, tenant_id, branch_id, name, username, CASE WHEN email_optional=1 THEN NULL ELSE email END AS email, email_optional, role, status, force_password_change, locked_until, created_at FROM users WHERE tenant_id=? ORDER BY id DESC"
        params = (scope,)
    with connection() as con:
        rows = con.execute(query, params).fetchall()
    return [row_dict(r) for r in rows]


def _check_worker_manager(con, worker_id, actor):
    target = con.execute("SELECT id,tenant_id,branch_id,role FROM users WHERE id=?", (worker_id,)).fetchone()
    if not target or target["role"] != "worker":
        raise HTTPException(status_code=404, detail="Trabajador no encontrado")
    if actor["role"] != "super_admin":
        tenant_scope(actor, target["tenant_id"])
    return target


@app.get("/api/users/{user_id}/access")
def get_worker_access(user_id: int, actor=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        _check_worker_manager(con, user_id, actor)
        permissions, schedule = _worker_access(con, user_id)
    return {"user_id": user_id, "permissions": permissions, "schedule": schedule}


@app.put("/api/users/{user_id}/access")
def update_worker_access(user_id: int, data: WorkerAccessInput, actor=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        target = _check_worker_manager(con, user_id, actor)
        permissions = {key: bool(data.permissions.get(key, True)) for key in WORKER_ACCESS_PERMISSIONS}
        schedule = []
        for item in data.schedule:
            weekday = int(item.get("weekday", -1))
            if weekday not in range(7):
                raise HTTPException(status_code=422, detail="Día laboral inválido")
            opens_at = str(item.get("opens_at", "00:00"))
            closes_at = str(item.get("closes_at", "23:59"))
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", opens_at) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", closes_at):
                raise HTTPException(status_code=422, detail="Hora laboral inválida")
            schedule.append({"weekday": weekday, "enabled": bool(item.get("enabled", False)), "opens_at": opens_at, "closes_at": closes_at})
        if len({item["weekday"] for item in schedule}) != len(schedule):
            raise HTTPException(status_code=422, detail="No repitas días laborales")
        con.execute("INSERT INTO worker_access(user_id,permissions_json,schedule_json,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(user_id) DO UPDATE SET permissions_json=excluded.permissions_json,schedule_json=excluded.schedule_json,updated_at=CURRENT_TIMESTAMP", (user_id, json.dumps(permissions), json.dumps(schedule)))
        audit(con, actor, "update", "worker_access", user_id, {"permissions": permissions, "schedule": schedule})
    return {"user_id": user_id, "permissions": permissions, "schedule": schedule}


@app.put("/api/worker-access/all")
def update_all_worker_access(data: WorkerAccessInput, actor=Depends(require("super_admin", "business_admin"))):
    if not data.tenant_id:
        raise HTTPException(status_code=422, detail="Selecciona un negocio")
    with connection() as con:
        if actor["role"] != "super_admin":
            tenant_scope(actor, data.tenant_id)
        workers = con.execute("SELECT id FROM users WHERE tenant_id=? AND role='worker' AND status='active'", (data.tenant_id,)).fetchall()
    for worker in workers:
        update_worker_access(worker["id"], data, actor)
    return {"updated": len(workers)}


@app.post("/api/users", status_code=status.HTTP_201_CREATED)
def create_user(data: UserInput, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    if data.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=422, detail="Rol inválido")
    if data.role == "super_admin" and user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="No puede crear superadministradores")
    scope = None if data.role == "super_admin" else tenant_scope(user, data.tenant_id)
    if user["role"] == "branch_admin" and (data.role != "worker" or data.branch_id != user["branch_id"]):
        raise HTTPException(status_code=403, detail="Solo puede crear trabajadores de su sucursal")
    username = normalize_username(data.username or (data.email or "").split("@")[0], data.name)
    email_optional = not bool(data.email and data.email.strip())
    stored_email = f"{username}@no-email.negrosky.local" if email_optional else data.email.strip().lower()
    try:
        with connection() as con:
            if data.branch_id:
                branch = con.execute("SELECT tenant_id FROM branches WHERE id=?", (data.branch_id,)).fetchone()
                if not branch or branch["tenant_id"] != scope:
                    raise HTTPException(status_code=422, detail="Sucursal inválida para el negocio")
            cur = con.execute(
                """INSERT INTO users
                (tenant_id, branch_id, name, username, email, email_optional, password_hash, role, force_password_change)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (scope, data.branch_id, data.name.strip(), username, stored_email, int(email_optional), hash_password(data.password), data.role),
            )
            user_id = cur.lastrowid
            audit(con, user, "create", "user", user_id, {"username": username, "email": data.email, "role": data.role})
            created = con.execute(
                "SELECT id, tenant_id, branch_id, name, username, CASE WHEN email_optional=1 THEN NULL ELSE email END AS email, role, status, force_password_change, created_at FROM users WHERE id=?", (user_id,)
            ).fetchone()
        return row_dict(created)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="El nombre de usuario o correo ya está registrado")


@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, actor=Depends(require("super_admin", "business_admin"))):
    username = normalize_username(data.username)
    with connection() as con:
        target = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if target["role"] == "super_admin" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="No puedes modificar un administrador general")
        scope = None if data.role == "super_admin" else tenant_scope(actor, data.tenant_id or target["tenant_id"])
        if data.role == "super_admin" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="No puedes asignar ese rol")
        if data.branch_id:
            branch = con.execute("SELECT tenant_id FROM branches WHERE id=?", (data.branch_id,)).fetchone()
            if not branch or branch["tenant_id"] != scope:
                raise HTTPException(status_code=422, detail="Sucursal inválida")
        optional = not bool(data.email and data.email.strip())
        email = f"{username}@no-email.negrosky.local" if optional else data.email.strip().lower()
        try:
            con.execute("""UPDATE users SET tenant_id=?,branch_id=?,name=?,username=?,email=?,email_optional=?,role=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (scope, data.branch_id, data.name.strip(), username, email, int(optional), data.role, user_id))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="El usuario o correo ya pertenece a otra cuenta")
        audit(con, actor, "update", "user", user_id, {"username": username, "role": data.role})
    return {"status": "updated", "id": user_id}


@app.put("/api/users/{user_id}/status")
def update_user_status(user_id: int, data: UserStatusInput, actor=Depends(require("super_admin", "business_admin"))):
    if user_id == actor["id"] and data.status != "active":
        raise HTTPException(status_code=409, detail="No puedes bloquear tu propia cuenta")
    with connection() as con:
        target = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if target["role"] == "super_admin" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="No puedes modificar esta cuenta")
        if actor["role"] != "super_admin":
            tenant_scope(actor, target["tenant_id"])
        con.execute("UPDATE users SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (data.status, user_id))
        if data.status != "active":
            con.execute("UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND revoked_at IS NULL", (user_id,))
        audit(con, actor, data.status, "user", user_id)
    return {"status": data.status}


@app.delete("/api/users/{user_id}")
def delete_worker(user_id: int, actor=Depends(require("super_admin", "business_admin"))):
    """Soft-delete a worker while retaining every sale and audit reference."""
    with connection() as con:
        target = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Trabajador no encontrado")
        if target["role"] != "worker":
            raise HTTPException(status_code=409, detail="Esta opción solo permite borrar trabajadores")
        if actor["role"] != "super_admin":
            tenant_scope(actor, target["tenant_id"])
    backup = create_backup("worker")
    with connection() as con:
        con.execute(
            "UPDATE users SET status='deleted', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (user_id,),
        )
        con.execute(
            "UPDATE user_sessions SET revoked_at=CURRENT_TIMESTAMP WHERE user_id=? AND revoked_at IS NULL",
            (user_id,),
        )
        audit(con, actor, "delete", "user", user_id,
              {"history_preserved": True, "backup": backup.name})
    return {
        "status": "deleted",
        "history_preserved": True,
        "message": "Trabajador retirado. Sus movimientos históricos permanecen guardados.",
        "backup": backup.name,
    }


@app.post("/api/users/{user_id}/support-code")
def generate_support_code(user_id: int, data: SupportCodeInput, actor=Depends(require("super_admin", "business_admin"))):
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(timezone.utc) + timedelta(minutes=data.minutes)
    with connection() as con:
        target = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if target["role"] == "super_admin" and actor["role"] != "super_admin":
            raise HTTPException(status_code=403, detail="No puedes recuperar esta cuenta")
        if actor["role"] != "super_admin":
            tenant_scope(actor, target["tenant_id"])
        con.execute("UPDATE support_codes SET used_at=CURRENT_TIMESTAMP WHERE user_id=? AND used_at IS NULL", (user_id,))
        con.execute("INSERT INTO support_codes (user_id,code_hash,expires_at,created_by) VALUES (?,?,?,?)",
                    (user_id, hash_password(code), expires.isoformat(), actor["id"]))
        audit(con, actor, "support_code", "user", user_id, {"minutes": data.minutes})
    return {"code": code, "expires_at": expires.isoformat(), "single_use": True}


@app.post("/api/users/{user_id}/force-password-change")
def force_password_change(user_id: int, actor=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        target = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if actor["role"] != "super_admin": tenant_scope(actor, target["tenant_id"])
        con.execute("UPDATE users SET force_password_change=1 WHERE id=?", (user_id,))
        audit(con, actor, "force_password_change", "user", user_id)
    return {"status": "required"}


@app.get("/api/customers")
def list_customers(tenant_id: int | None = None, q: str | None = None,
                   user=Depends(require("super_admin", "business_admin", "branch_admin", "worker"))):
    scope = tenant_scope(user, tenant_id)
    normalized = normalize_search(q or "")
    search = f"%{normalized}%"
    phone_search = f"%{''.join(ch for ch in (q or '') if ch.isdigit())}%"
    with connection() as con:
        rows = con.execute(
            """SELECT c.id, c.tenant_id, c.name, c.phone, c.marketing_consent, c.birth_date, c.birthday_consent, c.status, c.created_at,
            b.name AS origin_branch_name, t.name AS business_name FROM customers c
            JOIN tenants t ON t.id=c.tenant_id LEFT JOIN branches b ON b.id=c.origin_branch_id
            WHERE c.tenant_id=? AND (?='' OR c.search_key LIKE ? OR replace(replace(c.phone,' ',''),'+','') LIKE ?)
            ORDER BY c.search_key, c.id LIMIT 200""",
            (scope, normalized, search, phone_search),
        ).fetchall()
    return [row_dict(r) for r in rows]


@app.get("/api/birthday-settings")
def get_birthday_settings(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        con.execute("INSERT OR IGNORE INTO birthday_settings (tenant_id) VALUES (?)", (scope,))
        row = con.execute("SELECT * FROM birthday_settings WHERE tenant_id=?", (scope,)).fetchone()
    return {**row_dict(row), "enabled": bool(row["enabled"])}


@app.put("/api/birthday-settings")
def update_birthday_settings(data: BirthdaySettingsInput, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    with connection() as con:
        con.execute("INSERT INTO birthday_settings (tenant_id,enabled,days_before,monthly_limit,promotion,updated_at) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(tenant_id) DO UPDATE SET enabled=excluded.enabled,days_before=excluded.days_before,monthly_limit=excluded.monthly_limit,promotion=excluded.promotion,updated_at=CURRENT_TIMESTAMP", (scope, int(data.enabled), data.days_before, data.monthly_limit, data.promotion.strip()))
        row = con.execute("SELECT * FROM birthday_settings WHERE tenant_id=?", (scope,)).fetchone()
    return {**row_dict(row), "enabled": bool(row["enabled"])}


@app.get("/api/birthdays")
def list_birthdays(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    today = datetime.now().date()
    with connection() as con:
        settings = con.execute("SELECT * FROM birthday_settings WHERE tenant_id=?", (scope,)).fetchone()
        rows = con.execute("SELECT id,name,phone,birth_date,birthday_consent,marketing_consent FROM customers WHERE tenant_id=? AND status='active' AND birth_date IS NOT NULL AND birthday_consent=1 ORDER BY name", (scope,)).fetchall()
    days_before = int(settings["days_before"] if settings else 3)
    result = []
    for row in rows:
        try:
            birth = datetime.strptime(row["birth_date"], "%Y-%m-%d").date()
            birthday = birth.replace(year=today.year)
            if birthday < today:
                birthday = birthday.replace(year=today.year + 1)
            days = (birthday - today).days
            if days <= days_before:
                result.append({**row_dict(row), "days_until": days, "birthday_this_year": birthday.isoformat()})
        except (TypeError, ValueError):
            continue
    limit = int(settings["monthly_limit"] if settings else 0)
    if limit:
        result = result[:limit]
    return result


@app.post("/api/customers/assisted", status_code=status.HTTP_201_CREATED)
def assisted_customer(data: AssistedCustomerInput,
                      user=Depends(require("super_admin", "business_admin", "branch_admin", "worker"))):
    scope = tenant_scope(user, data.tenant_id)
    branch_id = data.branch_id or user.get("branch_id")
    phone = "".join(ch for ch in data.phone if ch.isdigit())
    with connection() as con:
        if branch_id:
            branch = con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=? AND status='active'", (branch_id, scope)).fetchone()
            if not branch:
                raise HTTPException(status_code=422, detail="Sucursal inválida")
        existing = con.execute("SELECT * FROM customers WHERE tenant_id=? AND phone=? AND status!='merged'", (scope, phone)).fetchone()
        if existing:
            return {"customer": row_dict(existing), "created": False, "message": "El cliente ya estaba registrado"}
        name = (data.name or f"Cliente {phone[-4:]}").strip()
        cur = con.execute("""INSERT INTO customers
            (tenant_id,name,phone,origin_branch_id,created_by_user_id,search_key) VALUES (?,?,?,?,?,?)""",
            (scope, name, phone, branch_id, user["id"], normalize_search(name)))
        customer_id = cur.lastrowid
        con.execute("""INSERT OR IGNORE INTO loyalty_cards (tenant_id,customer_id,program_id)
            SELECT tenant_id,?,id FROM loyalty_programs WHERE tenant_id=? AND status='active'""", (customer_id, scope))
        audit(con, user, "assisted_create", "customer", customer_id, {"phone": phone})
        customer = con.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    return {"customer": row_dict(customer), "created": True, "message": "Cliente registrado desde el panel del trabajador"}


@app.get("/api/customers/duplicates")
def customer_duplicates(tenant_id: int | None = None,
                        user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        rows = con.execute("""SELECT phone,COUNT(*) AS total,GROUP_CONCAT(id) AS customer_ids,
            GROUP_CONCAT(name,' | ') AS names FROM customers WHERE tenant_id=? AND status!='merged'
            GROUP BY replace(replace(phone,' ',''),'+57','') HAVING COUNT(*)>1""", (scope,)).fetchall()
    return [row_dict(row) for row in rows]


@app.post("/api/customers/merge")
def merge_customers(data: MergeCustomersInput,
                    user=Depends(require("super_admin", "business_admin"))):
    if data.primary_id == data.duplicate_id:
        raise HTTPException(status_code=422, detail="Selecciona dos clientes diferentes")
    backup = create_backup("merge")
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        primary = con.execute("SELECT * FROM customers WHERE id=?", (data.primary_id,)).fetchone()
        duplicate = con.execute("SELECT * FROM customers WHERE id=?", (data.duplicate_id,)).fetchone()
        if not primary or not duplicate or primary["tenant_id"] != duplicate["tenant_id"]:
            raise HTTPException(status_code=404, detail="Clientes no encontrados en el mismo negocio")
        tenant_scope(user, primary["tenant_id"])
        for card in con.execute("SELECT * FROM loyalty_cards WHERE customer_id=?", (data.duplicate_id,)).fetchall():
            current = con.execute("SELECT * FROM loyalty_cards WHERE customer_id=? AND program_id=?", (data.primary_id, card["program_id"])).fetchone()
            if current:
                con.execute("UPDATE loyalty_cards SET progress=?,cycle=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (max(current["progress"], card["progress"]), max(current["cycle"], card["cycle"]), current["id"]))
                con.execute("DELETE FROM loyalty_cards WHERE id=?", (card["id"],))
            else:
                con.execute("UPDATE loyalty_cards SET customer_id=? WHERE id=?", (data.primary_id, card["id"]))
        con.execute("UPDATE purchases SET customer_id=? WHERE customer_id=?", (data.primary_id, data.duplicate_id))
        con.execute("UPDATE operation_tokens SET customer_id=? WHERE customer_id=?", (data.primary_id, data.duplicate_id))
        for reward in con.execute("SELECT * FROM rewards WHERE customer_id=? ORDER BY id", (data.duplicate_id,)).fetchall():
            try:
                con.execute("UPDATE rewards SET customer_id=? WHERE id=?", (data.primary_id, reward["id"]))
            except sqlite3.IntegrityError:
                next_cycle = con.execute("SELECT COALESCE(MAX(card_cycle),0)+1 FROM rewards WHERE customer_id=? AND program_id=?", (data.primary_id, reward["program_id"])).fetchone()[0]
                con.execute("UPDATE rewards SET customer_id=?,card_cycle=? WHERE id=?", (data.primary_id, next_cycle, reward["id"]))
        combined_notes = "\n".join(x for x in [primary["notes"], duplicate["notes"]] if x)
        combined_tags = ", ".join(dict.fromkeys(x.strip() for x in f"{primary['tags'] or ''},{duplicate['tags'] or ''}".split(',') if x.strip()))
        con.execute("UPDATE customers SET notes=?,tags=? WHERE id=?", (combined_notes or None, combined_tags or None, data.primary_id))
        con.execute("UPDATE customers SET status='merged',merged_into_id=?,phone=? WHERE id=?",
                    (data.primary_id, f"merged-{data.duplicate_id}-{duplicate['phone']}", data.duplicate_id))
        audit(con, user, "merge", "customer", data.primary_id, {"duplicate_id": data.duplicate_id, "backup": backup.name})
    return {"status": "merged", "primary_id": data.primary_id, "duplicate_id": data.duplicate_id, "backup": backup.name}


@app.get("/api/customers/{customer_id}/profile")
def customer_profile(customer_id: int,
                     user=Depends(require("super_admin", "business_admin", "branch_admin", "worker"))):
    with connection() as con:
        customer = con.execute(
            """SELECT c.*, b.name AS origin_branch_name, b.city AS origin_branch_city,
            t.name AS business_name FROM customers c
            JOIN tenants t ON t.id=c.tenant_id
            LEFT JOIN branches b ON b.id=c.origin_branch_id WHERE c.id=?""",
            (customer_id,),
        ).fetchone()
        if not customer:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        tenant_scope(user, customer["tenant_id"])
        cards = con.execute(
            """SELECT lc.id, lc.progress, lc.cycle, lc.updated_at, lp.id AS program_id,
            lp.name AS program_name, lp.target_purchases, lp.reward_name, lp.progress_emoji,
            lp.status AS program_status,
            (SELECT COUNT(*) FROM rewards r WHERE r.customer_id=lc.customer_id
             AND r.program_id=lc.program_id AND r.status='available') AS available_rewards
            FROM loyalty_cards lc JOIN loyalty_programs lp ON lp.id=lc.program_id
            WHERE lc.customer_id=? ORDER BY lp.name""",
            (customer_id,),
        ).fetchall()
        purchases = con.execute(
            """SELECT p.id, p.created_at, lp.name AS program_name, b.name AS branch_name,
            u.name AS worker_name FROM purchases p
            JOIN loyalty_programs lp ON lp.id=p.program_id
            JOIN branches b ON b.id=p.branch_id JOIN users u ON u.id=p.worker_id
            WHERE p.customer_id=? ORDER BY p.id DESC LIMIT 100""",
            (customer_id,),
        ).fetchall()
        rewards = con.execute(
            """SELECT r.id, r.name, r.status, r.unlocked_at, r.claimed_at,
            lp.name AS program_name, b.name AS branch_name
            FROM rewards r JOIN loyalty_programs lp ON lp.id=r.program_id
            LEFT JOIN branches b ON b.id=r.branch_id
            WHERE r.customer_id=? ORDER BY r.id DESC LIMIT 100""",
            (customer_id,),
        ).fetchall()
        raffle_operations = con.execute("""SELECT x.id,x.code,x.ticket_ids_json,x.created_at,x.expires_at,x.used_at,x.rejected_at,
            x.validated_at,x.validated_by_name,r.name AS raffle_name
            FROM raffle_operation_tokens x JOIN raffles r ON r.id=x.raffle_id
            WHERE x.customer_id=? ORDER BY x.id DESC LIMIT 100""", (customer_id,)).fetchall()
        raffle_tickets = con.execute("""SELECT t.id,t.ticket_number,t.status,t.created_at,r.name AS raffle_name
            FROM raffle_tickets t JOIN raffles r ON r.id=t.raffle_id
            WHERE t.customer_phone=? AND r.tenant_id=? ORDER BY t.id DESC LIMIT 200""", (customer["phone"],customer["tenant_id"])).fetchall()
    return {
        "customer": row_dict(customer),
        "cards": [row_dict(row) for row in cards],
        "purchases": [row_dict(row) for row in purchases],
        "rewards": [row_dict(row) for row in rewards],
        "raffle_operations": [row_dict(row) for row in raffle_operations],
        "raffle_tickets": [row_dict(row) for row in raffle_tickets],
    }


@app.put("/api/customers/{customer_id}/meta")
def update_customer_meta(customer_id: int, data: CustomerMetaInput,
                         user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    with connection() as con:
        customer = con.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        if not customer:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        tenant_scope(user, customer["tenant_id"])
        con.execute("UPDATE customers SET notes=?,tags=? WHERE id=?", (data.notes, data.tags, customer_id))
        audit(con, user, "update_meta", "customer", customer_id)
    return {"status": "updated"}


@app.get("/api/loyalty-programs")
def list_programs(tenant_id: int | None = None, user=Depends(current_user)):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        if user["role"] != "super_admin" and not module_enabled(con, scope, "loyalty", user.get("branch_id")):
            return []
        rows = con.execute(
            """SELECT p.*, EXISTS(SELECT 1 FROM program_icons pi WHERE pi.program_id=p.id) AS has_custom_icon,
            COUNT(r.id) AS rewards_issued,
            CASE WHEN p.reward_stock IS NULL THEN NULL
                 ELSE MAX(p.reward_stock - COUNT(r.id), 0) END AS rewards_remaining
            FROM loyalty_programs p LEFT JOIN rewards r ON r.program_id=p.id
            WHERE p.tenant_id=? AND p.status!='trashed' GROUP BY p.id ORDER BY p.id DESC""",
            (scope,),
        ).fetchall()
    result = [row_dict(r) for r in rows]
    for item in result:
        item["icon_url"] = f"/api/public/loyalty-programs/{item['id']}/icon" if item.pop("has_custom_icon") else None
    return result


@app.get("/api/loyalty-programs/trash")
def list_program_trash(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        if user["role"] != "super_admin" and not module_enabled(con, scope, "loyalty", user.get("branch_id")):
            return []
        rows = con.execute(
            """SELECT p.*, EXISTS(SELECT 1 FROM program_icons pi WHERE pi.program_id=p.id) AS has_custom_icon,
            COUNT(r.id) AS rewards_issued,
            CASE WHEN p.reward_stock IS NULL THEN NULL
                 ELSE MAX(p.reward_stock - COUNT(r.id), 0) END AS rewards_remaining
            FROM loyalty_programs p LEFT JOIN rewards r ON r.program_id=p.id
            WHERE p.tenant_id=? AND p.status='trashed'
            GROUP BY p.id ORDER BY p.deleted_at DESC, p.id DESC""",
            (scope,),
        ).fetchall()
    result = [row_dict(r) for r in rows]
    for item in result:
        item["icon_url"] = f"/api/public/loyalty-programs/{item['id']}/icon" if item.pop("has_custom_icon") else None
    return result


def program_payload(con, program_id: int):
    program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()
    result = row_dict(program)
    if result:
        has_icon = con.execute("SELECT 1 FROM program_icons WHERE program_id=?", (program_id,)).fetchone()
        result["icon_url"] = f"/api/public/loyalty-programs/{program_id}/icon" if has_icon else None
    return result


@app.post("/api/loyalty-programs", status_code=status.HTTP_201_CREATED)
def create_program(data: LoyaltyProgramInput, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    stock = program_stock(data)
    with connection() as con:
        require_user_module(con, user, "loyalty")
        cur = con.execute(
            """INSERT INTO loyalty_programs
            (tenant_id, name, target_purchases, reward_name, progress_emoji, reward_stock, reward_display,
             title_mode,stamps_mode,progress_mode,reward_mode,button_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scope, data.name.strip(), data.target_purchases, data.reward_name.strip(), data.progress_emoji,
             stock, data.reward_display, data.title_mode, data.stamps_mode, data.progress_mode,
             data.reward_mode, data.button_mode),
        )
        program_id = cur.lastrowid
        con.execute(
            """INSERT OR IGNORE INTO loyalty_cards (tenant_id, customer_id, program_id)
            SELECT tenant_id, id, ? FROM customers WHERE tenant_id=? AND status='active'""",
            (program_id, scope),
        )
        audit(con, user, "create", "loyalty_program", program_id, data.model_dump())
        program = program_payload(con, program_id)
    return program

@app.put("/api/loyalty-programs/{program_id}")
def update_program(program_id: int, data: LoyaltyProgramUpdate, user=Depends(require("super_admin", "business_admin"))):
    stock = program_stock(data)
    with connection() as con:
        program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()
        if not program:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        tenant_scope(user, program["tenant_id"])
        require_user_module(con, user, "loyalty")
        if program["status"] == "trashed":
            raise HTTPException(status_code=409, detail="Restaura la campaña antes de editarla")
        con.execute("""UPDATE loyalty_programs SET name=?, target_purchases=?, reward_name=?,
        progress_emoji=?, reward_stock=?, reward_display=?,title_mode=?,stamps_mode=?,progress_mode=?,
        reward_mode=?,button_mode=? WHERE id=?""",
        (data.name.strip(), data.target_purchases, data.reward_name.strip(), data.progress_emoji, stock,
         data.reward_display, data.title_mode, data.stamps_mode, data.progress_mode, data.reward_mode,
         data.button_mode, program_id))
        audit(con, user, "update", "loyalty_program", program_id, data.model_dump())
        updated = program_payload(con, program_id)
    return updated


@app.post("/api/loyalty-programs/{program_id}/icon")
def update_program_icon(program_id: int, data: ProgramIconInput,
                        user=Depends(require("super_admin", "business_admin"))):
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", data.data_url)
    if not match:
        raise HTTPException(status_code=422, detail="Usa una imagen PNG, JPG o WebP")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="La imagen no es válida")
    if not content or len(content) > 1024 * 1024:
        raise HTTPException(status_code=413, detail="El icono debe pesar máximo 1 MB")
    mime = match.group(1)
    valid = ((mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or
             (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or
             (mime == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP"))
    if not valid:
        raise HTTPException(status_code=422, detail="El contenido de la imagen no coincide con su formato")
    with connection() as con:
        program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()
        if not program:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        tenant_scope(user, program["tenant_id"])
        require_user_module(con, user, "loyalty")
        con.execute("""INSERT INTO program_icons (program_id,tenant_id,icon_mime,icon_blob)
            VALUES (?,?,?,?) ON CONFLICT(program_id) DO UPDATE SET
            icon_mime=excluded.icon_mime,icon_blob=excluded.icon_blob,updated_at=CURRENT_TIMESTAMP""",
            (program_id, program["tenant_id"], mime, content))
        audit(con, user, "update_icon", "loyalty_program", program_id, {"mime": mime, "size": len(content)})
    return {"status": "saved", "icon_url": f"/api/public/loyalty-programs/{program_id}/icon"}


@app.delete("/api/loyalty-programs/{program_id}/icon")
def delete_program_icon(program_id: int,
                        user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()
        if not program:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        tenant_scope(user, program["tenant_id"])
        require_user_module(con, user, "loyalty")
        con.execute("DELETE FROM program_icons WHERE program_id=?", (program_id,))
        audit(con, user, "delete_icon", "loyalty_program", program_id)
    return {"status": "deleted"}


@app.get("/api/public/loyalty-programs/{program_id}/icon", include_in_schema=False)
def public_program_icon(program_id: int):
    with connection() as con:
        row = con.execute("""SELECT i.icon_mime,i.icon_blob FROM program_icons i
            JOIN loyalty_programs p ON p.id=i.program_id
            JOIN tenants t ON t.id=p.tenant_id
            WHERE i.program_id=? AND p.status='active' AND t.status='active'""", (program_id,)).fetchone()
        if row:
            require_public_module(con, con.execute("SELECT tenant_id FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()["tenant_id"], "public_page")
    if not row:
        raise HTTPException(status_code=404, detail="Icono no encontrado")
    return StreamingResponse(io.BytesIO(row["icon_blob"]), media_type=row["icon_mime"],
                             headers={"Cache-Control": "public, max-age=300"})

@app.put("/api/loyalty-programs/{program_id}/status")
def update_program_status(program_id: int, data: LoyaltyProgramStatusUpdate, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()
        if not program:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        tenant_scope(user, program["tenant_id"])
        require_user_module(con, user, "loyalty")
        if program["status"] == "trashed":
            raise HTTPException(status_code=409, detail="Restaura la campaña desde la papelera")
        new_status = "active" if data.active else "paused"
        con.execute("UPDATE loyalty_programs SET status=? WHERE id=?", (new_status, program_id))
        audit(con, user, "resume" if data.active else "pause", "loyalty_program", program_id, {"status": new_status})
        updated = program_payload(con, program_id)
    return updated


@app.delete("/api/loyalty-programs/{program_id}")
def trash_program(program_id: int, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()
        if not program:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        tenant_scope(user, program["tenant_id"])
        require_user_module(con, user, "loyalty")
        if program["status"] == "trashed":
            raise HTTPException(status_code=409, detail="La campaña ya está en la papelera")
        con.execute(
            "UPDATE loyalty_programs SET status='trashed', deleted_at=CURRENT_TIMESTAMP WHERE id=?",
            (program_id,),
        )
        audit(con, user, "trash", "loyalty_program", program_id, {"previous_status": program["status"]})
    return {"status": "trashed", "id": program_id, "progress_preserved": True}


@app.put("/api/loyalty-programs/{program_id}/restore")
def restore_program(program_id: int, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (program_id,)).fetchone()
        if not program:
            raise HTTPException(status_code=404, detail="Campaña no encontrada")
        tenant_scope(user, program["tenant_id"])
        require_user_module(con, user, "loyalty")
        if program["status"] != "trashed":
            raise HTTPException(status_code=409, detail="La campaña no está en la papelera")
        con.execute(
            "UPDATE loyalty_programs SET status='active', deleted_at=NULL WHERE id=?",
            (program_id,),
        )
        con.execute(
            """INSERT OR IGNORE INTO loyalty_cards (tenant_id, customer_id, program_id)
            SELECT tenant_id, id, ? FROM customers WHERE tenant_id=? AND status='active'""",
            (program_id, program["tenant_id"]),
        )
        audit(con, user, "restore", "loyalty_program", program_id, {"status": "active"})
        restored = program_payload(con, program_id)
    return restored


@app.post("/api/public/{slug}/identify")
def identify_customer(slug: str, data: CustomerIdentifyInput):
    phone = "".join(ch for ch in data.phone if ch.isdigit() or ch == "+")
    with connection() as con:
        tenant = con.execute("SELECT * FROM tenants WHERE slug=? AND status='active'", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page", data.branch_id)
        if data.branch_id is not None:
            branch = con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=?", (data.branch_id, tenant["id"])).fetchone()
            if not branch:
                raise HTTPException(status_code=422, detail="Sucursal inválida")
        customer = con.execute("SELECT * FROM customers WHERE tenant_id=? AND phone=?", (tenant["id"], phone)).fetchone()
        if customer:
            con.execute(
                "UPDATE customers SET name=?, search_key=?, marketing_consent=?, origin_branch_id=?, birth_date=COALESCE(?,birth_date), birthday_consent=COALESCE(?,birthday_consent) WHERE id=?",
                (data.name.strip(), normalize_search(data.name), int(data.marketing_consent), data.branch_id if data.branch_id is not None else customer["origin_branch_id"], data.birth_date, None if data.birthday_consent is None else int(data.birthday_consent), customer["id"]),
            )
            customer = con.execute("SELECT * FROM customers WHERE id=?", (customer["id"],)).fetchone()
        else:
            cur = con.execute(
                "INSERT INTO customers (tenant_id, name, search_key, phone, marketing_consent, origin_branch_id, birth_date, birthday_consent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tenant["id"], data.name.strip(), normalize_search(data.name), phone, int(data.marketing_consent), data.branch_id, data.birth_date, int(bool(data.birthday_consent))),
            )
            customer_id = cur.lastrowid
            con.execute(
                """INSERT INTO loyalty_cards (tenant_id, customer_id, program_id)
                SELECT tenant_id, ?, id FROM loyalty_programs WHERE tenant_id=? AND status='active'""",
                (customer_id, tenant["id"]),
            )
            customer = con.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
    safe = row_dict(customer)
    return {"customer": safe, "access_token": create_customer_token(safe), "token_type": "bearer"}

@app.get("/api/public/{slug}/branches")
def public_branches(slug: str):
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=? AND status='active'", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page")
        rows = con.execute("SELECT id, name, city, address FROM branches WHERE tenant_id=? AND status='active' ORDER BY name", (tenant["id"],)).fetchall()
    return [row_dict(row) for row in rows]


@app.get("/api/public/{slug}/service-status")
def public_service_status(slug: str, branch_id: int | None = None):
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=?", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page", branch_id)
        return service_status(con, tenant["id"], branch_id)


@app.get("/api/public/me/cards")
def customer_cards(customer=Depends(current_customer)):
    with connection() as con:
        require_public_module(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id"))
        loyalty_on = module_enabled(con, customer["tenant_id"], "loyalty", customer.get("origin_branch_id"))
        if not loyalty_on:
            return {"customer": customer, "cards": [], "rewards": [],
                    "enabled_modules": effective_modules(con, customer["tenant_id"], customer.get("origin_branch_id")),
                    "module_disabled": "loyalty"}
        cards = con.execute(
            """SELECT c.id, c.progress, c.cycle, p.id AS program_id, p.name AS program_name,
            p.target_purchases, p.reward_name, p.progress_emoji, p.reward_stock, p.reward_display,
            p.title_mode,p.stamps_mode,p.progress_mode,p.reward_mode,p.button_mode,
            EXISTS(SELECT 1 FROM program_icons pi WHERE pi.program_id=p.id) AS has_custom_icon,
            CASE WHEN p.reward_stock IS NULL THEN NULL ELSE MAX(p.reward_stock -
            (SELECT COUNT(*) FROM rewards r WHERE r.program_id=p.id), 0) END AS rewards_remaining
            FROM loyalty_cards c JOIN loyalty_programs p ON p.id=c.program_id
            WHERE c.customer_id=? AND p.status='active' ORDER BY p.id""",
            (customer["id"],),
        ).fetchall()
        brand_defaults = branding_payload(con, customer["tenant_id"])
        rewards = con.execute(
            """SELECT r.id, r.program_id, r.name, r.status, r.unlocked_at, r.claimed_at,
            p.name AS program_name FROM rewards r JOIN loyalty_programs p ON p.id=r.program_id
            WHERE r.customer_id=? ORDER BY r.id DESC""",
            (customer["id"],),
        ).fetchall()
        enabled_modules = effective_modules(con, customer["tenant_id"], customer.get("origin_branch_id"))
    card_items = [row_dict(r) for r in cards]
    for item in card_items:
        item["icon_url"] = f"/api/public/loyalty-programs/{item['program_id']}/icon" if item.pop("has_custom_icon") else None
        for part in ("title", "stamps", "progress", "reward", "button"):
            mode = item.pop(f"{part}_mode")
            item[f"show_{part}"] = mode == "show" or (mode == "inherit" and brand_defaults[f"show_campaign_{part}"])
    return {"customer": customer, "cards": card_items, "rewards": [row_dict(r) for r in rewards],
            "enabled_modules": enabled_modules}

@app.get("/api/public/me/raffles")
def customer_raffles(customer=Depends(current_customer)):
    with connection() as con:
        if not module_enabled(con, customer["tenant_id"], "raffles", customer.get("origin_branch_id")):
            return []
        rows=con.execute("SELECT * FROM raffles WHERE tenant_id=? AND status='active' ORDER BY id DESC",(customer["tenant_id"],)).fetchall(); out=[]
        for r in rows:
            mine=con.execute("SELECT COUNT(*) n FROM raffle_tickets WHERE raffle_id=? AND customer_phone=?",(r["id"],customer.get("phone"))).fetchone()["n"]
            total=con.execute("SELECT COUNT(*) n FROM raffle_tickets WHERE raffle_id=? AND status IN ('pending','reserved','winner')",(r["id"],)).fetchone()["n"]
            out.append({**row_dict(r),"my_tickets":mine,"tickets_used":total,"tickets_available":None if not r["ticket_count"] else max(0,r["ticket_count"]-total)})
        return out

@app.post("/api/public/me/raffles/{raffle_id}/participate", status_code=201)
def participate_raffle(raffle_id:int, data: dict | None = None, request: Request = None, customer=Depends(current_customer)):
    with connection() as con:
        if not module_enabled(con, customer["tenant_id"], "raffles", customer.get("origin_branch_id")):
            raise HTTPException(404,"Rifas no disponibles")
        r=con.execute("SELECT * FROM raffles WHERE id=? AND tenant_id=? AND status='active'",(raffle_id,customer["tenant_id"])).fetchone()
        if not r: raise HTTPException(404,"Rifa no disponible")
        # La cantidad permitida se aplica por compra. Las compras validadas no
        # bloquean una nueva compra del mismo cliente.
        current=0
        available=None if not r["ticket_count"] else r["ticket_count"]-con.execute("SELECT COUNT(*) n FROM raffle_tickets WHERE raffle_id=? AND status IN ('pending','reserved','winner')",(raffle_id,)).fetchone()["n"]
        qty=max(1,int(r["tickets_per_purchase"] or 1))
        if available is not None: qty=min(qty,available)
        if qty<=0: raise HTTPException(409,"No quedan boletas disponibles")
        requested=[str(x).strip() for x in ((data or {}).get('ticket_numbers') or [])]
        if requested:
            if len(set(requested)) != qty: raise HTTPException(409,f"Debes escoger exactamente {qty} boleta(s)")
            for number in requested:
                if not number.isdigit() or int(number)<1 or (r["ticket_count"] and int(number)>r["ticket_count"]): raise HTTPException(422,"Número de boleta inválido")
                if con.execute("SELECT 1 FROM raffle_tickets WHERE raffle_id=? AND ticket_number=?",(raffle_id,number)).fetchone(): raise HTTPException(409,f"La boleta {number} ya no está disponible")
            numbers=requested
        else:
            numbers=[]
            for _ in range(qty):
                number=secrets.token_hex(4).upper()
                while con.execute("SELECT 1 FROM raffle_tickets WHERE raffle_id=? AND ticket_number=?",(raffle_id,number)).fetchone(): number=secrets.token_hex(4).upper()
                numbers.append(number)
        created=[];created_codes=[]
        for number in numbers:
            cur=con.execute("INSERT INTO raffle_tickets(raffle_id,ticket_number,customer_name,customer_phone,status) VALUES(?,?,?,?, 'pending')",(raffle_id,number,customer["name"],customer.get("phone"))); created.append(cur.lastrowid);created_codes.append(number)
        expires=datetime.now(timezone.utc)+timedelta(seconds=300)
        code=new_operation_code(con)
        con.execute("INSERT INTO raffle_operation_tokens(tenant_id,customer_id,raffle_id,branch_id,code,ticket_ids_json,expires_at) VALUES(?,?,?,?,?,?,?)",(customer["tenant_id"],customer["id"],raffle_id,customer.get("origin_branch_id"),code,json.dumps(created),expires.isoformat()))
        return {"raffle_id":raffle_id,"requested":qty,"status":"pending","message":"Participación pendiente. El negocio debe permitirla.","ticket_ids":created,"ticket_codes":created_codes,"code":code,"expires_in_seconds":300,"worker_url":worker_link(request,code) if request else None}

@app.get("/api/public/me/raffle-operations")
def customer_raffle_operations(customer=Depends(current_customer)):
    with connection() as con:
        rows = con.execute("""SELECT x.*, r.name raffle_name
            FROM raffle_operation_tokens x JOIN raffles r ON r.id=x.raffle_id
            WHERE x.customer_id=? ORDER BY x.id DESC LIMIT 20""", (customer["id"],)).fetchall()
        result=[]
        for token in rows:
            ids=json.loads(token["ticket_ids_json"] or "[]")
            marks=','.join('?'*len(ids)) or 'NULL'
            tickets=con.execute(f"SELECT ticket_number FROM raffle_tickets WHERE id IN ({marks}) ORDER BY CAST(ticket_number AS INTEGER),id",ids).fetchall() if ids else []
            status_name="validated" if token["used_at"] else "rejected" if token["rejected_at"] else "expired" if datetime.fromisoformat(token["expires_at"]) < datetime.now(timezone.utc) else "pending"
            result.append({"id":token["id"],"raffle_id":token["raffle_id"],"raffle_name":token["raffle_name"],"code":token["code"],"status":status_name,"ticket_numbers":[x["ticket_number"] for x in tickets],"created_at":token["created_at"],"validated_at":token["validated_at"],"seller_name":token["validated_by_name"]})
        return result

@app.get("/api/public/{slug}/raffles")
def public_raffles_by_slug(slug: str):
    """Public listing: the page URL is the source of tenant identity."""
    with connection() as con:
        tenant=con.execute("SELECT * FROM tenants WHERE slug=? AND status='active'",(slug,)).fetchone()
        if not tenant: raise HTTPException(404,"Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page")
        if not module_enabled(con, tenant["id"], "raffles"): return []
        rows=con.execute("SELECT * FROM raffles WHERE tenant_id=? AND status='active' ORDER BY id DESC",(tenant["id"],)).fetchall()
        out=[]
        for r in rows:
            total=con.execute("SELECT COUNT(*) n FROM raffle_tickets WHERE raffle_id=? AND status IN ('pending','reserved','winner')",(r["id"],)).fetchone()["n"]
            out.append({**row_dict(r),"my_tickets":0,"tickets_used":total,"tickets_available":None if not r["ticket_count"] else max(0,r["ticket_count"]-total)})
        return out

@app.get("/api/public/me/roulette")
def customer_roulette(customer=Depends(current_customer)):
    with connection() as con:
        if not module_enabled(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id")):
            return []
        if not module_enabled(con, customer["tenant_id"], "roulette", customer.get("origin_branch_id")):
            return []
        rows=con.execute("SELECT id,name,prizes_json,difficulty FROM roulette_configs WHERE tenant_id=? AND enabled=1 ORDER BY id DESC",(customer["tenant_id"],)).fetchall()
        return [{"id":r["id"],"name":r["name"],"prizes":json.loads(r["prizes_json"]),"difficulty":r["difficulty"]} for r in rows]

@app.get("/api/public/{slug}/roulette")
def public_roulette_by_slug(slug: str):
    """Public listing scoped strictly by the business URL."""
    with connection() as con:
        tenant=con.execute("SELECT * FROM tenants WHERE slug=? AND status='active'",(slug,)).fetchone()
        if not tenant: raise HTTPException(404,"Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page")
        if not module_enabled(con, tenant["id"], "roulette"): return []
        rows=con.execute("SELECT id,name,prizes_json,difficulty FROM roulette_configs WHERE tenant_id=? AND enabled=1 ORDER BY id DESC",(tenant["id"],)).fetchall()
        return [{"id":r["id"],"name":r["name"],"prizes":json.loads(r["prizes_json"]),"difficulty":r["difficulty"]} for r in rows]


@app.get("/api/public/me/history")
def customer_history(customer=Depends(current_customer)):
    with connection() as con:
        require_public_module(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id"))
        purchases = con.execute(
            """SELECT p.id, p.created_at, lp.name AS program_name, b.name AS branch_name
            FROM purchases p
            JOIN loyalty_programs lp ON lp.id=p.program_id
            JOIN branches b ON b.id=p.branch_id
            WHERE p.customer_id=? AND p.tenant_id=?
            ORDER BY p.id DESC""",
            (customer["id"], customer["tenant_id"]),
        ).fetchall()
        rewards = con.execute(
            """SELECT r.id, r.name, r.status, r.unlocked_at, r.claimed_at,
            lp.name AS program_name, b.name AS branch_name
            FROM rewards r
            JOIN loyalty_programs lp ON lp.id=r.program_id
            LEFT JOIN branches b ON b.id=r.branch_id
            WHERE r.customer_id=? AND r.tenant_id=?
            ORDER BY r.id DESC""",
            (customer["id"], customer["tenant_id"]),
        ).fetchall()
    purchase_rows = [row_dict(row) for row in purchases]
    reward_rows = [row_dict(row) for row in rewards]
    return {
        "summary": {
            "purchases": len(purchase_rows),
            "rewards_earned": len(reward_rows),
            "rewards_claimed": sum(1 for reward in reward_rows if reward["status"] == "used"),
        },
        "purchases": purchase_rows,
        "rewards": reward_rows,
    }


@app.post("/api/public/me/purchase-token")
def create_purchase_token(data: OperationTokenInput, request: Request, customer=Depends(current_customer)):
    expires = datetime.now(timezone.utc) + timedelta(seconds=60)
    with connection() as con:
        require_public_module(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id"))
        require_service_open(con, customer["tenant_id"], customer.get("origin_branch_id"))
        require_module(con, customer["tenant_id"], "loyalty", customer.get("origin_branch_id"))
        code = new_operation_code(con)
        card = con.execute(
            """SELECT c.id, p.reward_stock,
            (SELECT COUNT(*) FROM rewards r WHERE r.program_id=p.id) AS rewards_issued
            FROM loyalty_cards c JOIN loyalty_programs p ON p.id=c.program_id
            WHERE c.customer_id=? AND c.program_id=? AND c.tenant_id=? AND p.status='active'""",
            (customer["id"], data.program_id, customer["tenant_id"]),
        ).fetchone()
        if not card:
            raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
        if card["reward_stock"] is not None and card["rewards_issued"] >= card["reward_stock"]:
            raise HTTPException(status_code=409, detail="Premios agotados. Esta campaña ha entregado todos los premios disponibles.")
        con.execute(
            """INSERT INTO operation_tokens
            (tenant_id, customer_id, program_id, operation_type, branch_id, code, expires_at)
            VALUES (?, ?, ?, 'purchase', ?, ?, ?)""",
            (customer["tenant_id"], customer["id"], data.program_id, customer.get("origin_branch_id"), code, expires.isoformat()),
        )
    return {"code": code, "expires_in_seconds": 60, "operation": "purchase", "worker_url": worker_link(request, code)}

@app.get("/api/business/history")
def business_history(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope=tenant_scope(user,tenant_id)
    with connection() as con:
        p=con.execute("SELECT p.created_at,c.name customer_name,lp.name program_name,b.name branch_name,u.name worker_name FROM purchases p JOIN customers c ON c.id=p.customer_id JOIN loyalty_programs lp ON lp.id=p.program_id JOIN branches b ON b.id=p.branch_id JOIN users u ON u.id=p.worker_id WHERE p.tenant_id=? ORDER BY p.id DESC LIMIT 200",(scope,)).fetchall()
        r=con.execute("SELECT r.claimed_at,c.name customer_name,r.name reward_name,b.name branch_name,u.name worker_name FROM rewards r JOIN customers c ON c.id=r.customer_id LEFT JOIN branches b ON b.id=r.branch_id LEFT JOIN users u ON u.id=r.worker_id WHERE r.tenant_id=? AND r.status='used' ORDER BY r.id DESC LIMIT 200",(scope,)).fetchall()
    return {"purchases":[row_dict(x) for x in p],"rewards":[row_dict(x) for x in r]}


@app.get("/api/public/me/operation-status/{code}")
def public_operation_status(code: str, customer=Depends(current_customer)):
    now = datetime.now(timezone.utc)
    with connection() as con:
        require_public_module(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id"))
        token = con.execute(
            """SELECT * FROM operation_tokens
            WHERE code=? AND customer_id=? AND tenant_id=?""",
            (code, customer["id"], customer["tenant_id"]),
        ).fetchone()
        if not token:
            raise HTTPException(status_code=404, detail="Código no encontrado")
        if token["used_at"]:
            result = {"status": "validated", "operation": token["operation_type"]}
            if token["operation_type"] == "purchase":
                card = con.execute(
                    """SELECT c.progress, p.target_purchases, p.reward_name
                    FROM loyalty_cards c JOIN loyalty_programs p ON p.id=c.program_id
                    WHERE c.customer_id=? AND c.program_id=?""",
                    (customer["id"], token["program_id"]),
                ).fetchone()
                if card:
                    result.update(row_dict(card))
                    result["mission_completed"] = card["progress"] == 0
                    result["reward_name"] = card["reward_name"]
            return result
        if datetime.fromisoformat(token["expires_at"]) < now:
            return {"status": "expired", "operation": token["operation_type"]}
    return {"status": "pending", "operation": token["operation_type"]}


@app.get("/api/operations/preview/{code}")
def preview_operation(code: str, user=Depends(require("worker", "branch_admin"))):
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=422, detail="El código debe tener seis números")
    now = datetime.now(timezone.utc)
    with connection() as con:
        require_service_open(con, user["tenant_id"], user["branch_id"])
        require_user_module(con, user, "loyalty", user["branch_id"])
        require_worker_access(con, user, "validate_purchase")
        token = con.execute(
            """SELECT ot.*, c.name AS customer_name, c.phone AS customer_phone,
            p.name AS program_name, p.reward_name
            FROM operation_tokens ot
            JOIN customers c ON c.id=ot.customer_id
            JOIN loyalty_programs p ON p.id=ot.program_id
            WHERE ot.code=? AND ot.tenant_id=?""",
            (code, user["tenant_id"]),
        ).fetchone()
        if not token:
            raise HTTPException(status_code=404, detail="Código no válido para este negocio")
        if token["branch_id"] is not None and token["branch_id"] != user["branch_id"]:
            raise HTTPException(status_code=403, detail="Este QR pertenece a otra sucursal")
        if token["used_at"]:
            raise HTTPException(status_code=409, detail="Este código ya fue utilizado")
        if datetime.fromisoformat(token["expires_at"]) < now:
            raise HTTPException(status_code=409, detail="Este código venció. El cliente ya puede mostrar el nuevo código.")
        quantity = 1
        if token["operation_type"] == "reward_batch":
            quantity = con.execute(
                "SELECT COUNT(*) FROM operation_token_rewards WHERE operation_token_id=?", (token["id"],)
            ).fetchone()[0]
        return {
            "code": code,
            "operation": token["operation_type"],
            "customer_name": token["customer_name"],
            "customer_phone": token["customer_phone"],
            "program_name": token["program_name"],
            "reward_name": token["reward_name"],
            "quantity": quantity,
            "expires_at": token["expires_at"],
        }


@app.post("/api/operations/validate-purchase")
def validate_purchase(data: ValidateOperationInput, user=Depends(require("worker", "branch_admin"))):
    if not user["branch_id"]:
        raise HTTPException(status_code=422, detail="El usuario debe tener una sucursal")
    now = datetime.now(timezone.utc)
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        require_service_open(con, user["tenant_id"], user["branch_id"])
        require_user_module(con, user, "loyalty", user["branch_id"])
        require_worker_access(con, user, "validate_purchase")
        token = con.execute("SELECT * FROM operation_tokens WHERE code=? AND operation_type='purchase'", (data.code,)).fetchone()
        if not token or token["tenant_id"] != user["tenant_id"]:
            raise HTTPException(status_code=404, detail="Código no válido para este negocio")
        if token["branch_id"] is not None and token["branch_id"] != user["branch_id"]:
            raise HTTPException(status_code=403, detail="Este QR pertenece a otra sucursal")
        if token["used_at"] or datetime.fromisoformat(token["expires_at"]) < now:
            raise HTTPException(status_code=409, detail="Código utilizado o vencido")
        card = con.execute("SELECT * FROM loyalty_cards WHERE customer_id=? AND program_id=?", (token["customer_id"], token["program_id"])).fetchone()
        program = con.execute("SELECT * FROM loyalty_programs WHERE id=?", (token["program_id"],)).fetchone()
        new_progress = card["progress"] + 1
        reward = None
        if new_progress >= program["target_purchases"]:
            if program["reward_stock"] is not None:
                issued = con.execute("SELECT COUNT(*) FROM rewards WHERE program_id=?", (program["id"],)).fetchone()[0]
                if issued >= program["reward_stock"]:
                    raise HTTPException(status_code=409, detail="Premios agotados. No es posible registrar más compras en esta campaña.")
            con.execute(
                """INSERT INTO rewards (tenant_id, customer_id, program_id, card_cycle, name)
                VALUES (?, ?, ?, ?, ?)""",
                (token["tenant_id"], token["customer_id"], token["program_id"], card["cycle"], program["reward_name"]),
            )
            reward = row_dict(con.execute("SELECT * FROM rewards WHERE id=last_insert_rowid()").fetchone())
            con.execute("UPDATE loyalty_cards SET progress=0, cycle=cycle+1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (card["id"],))
            new_progress = 0
        else:
            con.execute("UPDATE loyalty_cards SET progress=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_progress, card["id"]))
        con.execute("UPDATE operation_tokens SET used_at=? WHERE id=?", (now.isoformat(), token["id"]))
        cur = con.execute(
            """INSERT INTO purchases
            (tenant_id, branch_id, customer_id, program_id, worker_id, operation_token_id)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (token["tenant_id"], user["branch_id"], token["customer_id"], token["program_id"], user["id"], token["id"]),
        )
        audit(con, user, "validate", "purchase", cur.lastrowid, {"customer_id": token["customer_id"]})
        customer_row = con.execute("SELECT name FROM customers WHERE id=?", (token["customer_id"],)).fetchone()
        add_notification(
            con, token["tenant_id"], user["branch_id"], token["customer_id"], "purchase",
            "Nueva compra validada",
            f"{user['name']} registró una compra de {customer_row['name']} en {program['name']}.",
        )
    with connection() as con:
        customer_name = con.execute("SELECT name FROM customers WHERE id=?", (token["customer_id"],)).fetchone()["name"]
    return {"status": "validated", "customer_name": customer_name, "progress": new_progress, "target": program["target_purchases"], "reward": reward}


@app.post("/api/public/me/rewards/{reward_id}/token")
def create_reward_token(reward_id: int, request: Request, customer=Depends(current_customer)):
    expires = datetime.now(timezone.utc) + timedelta(seconds=60)
    with connection() as con:
        require_public_module(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id"))
        require_service_open(con, customer["tenant_id"], customer.get("origin_branch_id"))
        require_module(con, customer["tenant_id"], "loyalty", customer.get("origin_branch_id"))
        code = new_operation_code(con)
        reward = con.execute("SELECT * FROM rewards WHERE id=? AND customer_id=? AND status='available'", (reward_id, customer["id"])).fetchone()
        if not reward:
            raise HTTPException(status_code=404, detail="Premio no disponible")
        con.execute(
            """INSERT INTO operation_tokens
            (tenant_id, customer_id, program_id, operation_type, reference_id, branch_id, code, expires_at)
            VALUES (?, ?, ?, 'reward', ?, ?, ?, ?)""",
            (customer["tenant_id"], customer["id"], reward["program_id"], reward_id, customer.get("origin_branch_id"), code, expires.isoformat()),
        )
    return {"code": code, "expires_in_seconds": 60, "operation": "reward", "worker_url": worker_link(request, code)}

@app.post("/api/public/me/rewards/batch-token")
def create_reward_batch_token(data: RewardBatchInput, request: Request, customer=Depends(current_customer)):
    expires = datetime.now(timezone.utc) + timedelta(seconds=60)
    with connection() as con:
        require_public_module(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id"))
        require_service_open(con, customer["tenant_id"], customer.get("origin_branch_id"))
        require_module(con, customer["tenant_id"], "loyalty", customer.get("origin_branch_id"))
        rewards = con.execute(
            """SELECT id, name FROM rewards WHERE customer_id=? AND tenant_id=?
            AND program_id=? AND status='available' ORDER BY id LIMIT ?""",
            (customer["id"], customer["tenant_id"], data.program_id, data.quantity),
        ).fetchall()
        if len(rewards) != data.quantity:
            raise HTTPException(status_code=409, detail="No hay suficientes premios disponibles para esa cantidad")
        code = new_operation_code(con)
        cur = con.execute(
            """INSERT INTO operation_tokens
            (tenant_id, customer_id, program_id, operation_type, branch_id, code, expires_at)
            VALUES (?, ?, ?, 'reward_batch', ?, ?, ?)""",
            (customer["tenant_id"], customer["id"], data.program_id, customer.get("origin_branch_id"), code, expires.isoformat()),
        )
        con.executemany(
            "INSERT INTO operation_token_rewards (operation_token_id, reward_id) VALUES (?, ?)",
            [(cur.lastrowid, reward["id"]) for reward in rewards],
        )
    return {"code": code, "expires_in_seconds": 60, "operation": "reward_batch", "quantity": data.quantity, "name": rewards[0]["name"], "worker_url": worker_link(request, code)}


@app.post("/api/operations/validate-reward")
def validate_reward(data: ValidateOperationInput, user=Depends(require("worker", "branch_admin"))):
    if not user["branch_id"]:
        raise HTTPException(status_code=422, detail="El usuario debe tener una sucursal")
    now = datetime.now(timezone.utc)
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        require_service_open(con, user["tenant_id"], user["branch_id"])
        require_user_module(con, user, "loyalty", user["branch_id"])
        require_worker_access(con, user, "validate_reward")
        token = con.execute("SELECT * FROM operation_tokens WHERE code=? AND operation_type IN ('reward','reward_batch')", (data.code,)).fetchone()
        if not token or token["tenant_id"] != user["tenant_id"]:
            raise HTTPException(status_code=404, detail="Código no válido para este negocio")
        if token["branch_id"] is not None and token["branch_id"] != user["branch_id"]:
            raise HTTPException(status_code=403, detail="Este QR pertenece a otra sucursal")
        if token["used_at"] or datetime.fromisoformat(token["expires_at"]) < now:
            raise HTTPException(status_code=409, detail="Código utilizado o vencido")
        if token["operation_type"] == "reward_batch":
            rewards = con.execute(
                """SELECT r.* FROM rewards r JOIN operation_token_rewards m ON m.reward_id=r.id
                WHERE m.operation_token_id=? AND r.status='available' ORDER BY r.id""",
                (token["id"],),
            ).fetchall()
            requested = con.execute("SELECT COUNT(*) FROM operation_token_rewards WHERE operation_token_id=?", (token["id"],)).fetchone()[0]
            if len(rewards) != requested:
                raise HTTPException(status_code=409, detail="Uno o más premios ya fueron utilizados")
        else:
            reward = con.execute("SELECT * FROM rewards WHERE id=? AND status='available'", (token["reference_id"],)).fetchone()
            if not reward:
                raise HTTPException(status_code=409, detail="Premio ya utilizado")
            rewards = [reward]
        con.executemany(
            "UPDATE rewards SET status='used', claimed_at=?, branch_id=?, worker_id=? WHERE id=?",
            [(now.isoformat(), user["branch_id"], user["id"], reward["id"]) for reward in rewards],
        )
        con.execute("UPDATE operation_tokens SET used_at=? WHERE id=?", (now.isoformat(), token["id"]))
        audit(con, user, "validate", "reward", rewards[0]["id"], {"customer_id": rewards[0]["customer_id"], "quantity": len(rewards)})
        customer_row = con.execute("SELECT name FROM customers WHERE id=?", (token["customer_id"],)).fetchone()
        add_notification(
            con, token["tenant_id"], user["branch_id"], token["customer_id"], "reward",
            "Premio entregado",
            f"{user['name']} entregó {len(rewards)} premio(s) a {customer_row['name']}: {rewards[0]['name']}.",
        )
    with connection() as con:
        customer_name = con.execute("SELECT name FROM customers WHERE id=?", (token["customer_id"],)).fetchone()["name"]
    return {"status": "used", "customer_name": customer_name, "reward_id": rewards[0]["id"], "name": rewards[0]["name"], "count": len(rewards)}


@app.get("/api/appointment-services")
def list_appointment_services(tenant_id: int | None = None, branch_id: int | None = None,
                              user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    if user["role"] == "branch_admin":
        branch_id = user["branch_id"]
    with connection() as con:
        require_user_module(con, user, "appointments", branch_id)
        query = "SELECT * FROM appointment_services WHERE tenant_id=?"
        params = [scope]
        if branch_id is not None:
            query += " AND (branch_id IS NULL OR branch_id=?)"
            params.append(branch_id)
        rows = con.execute(query + " ORDER BY status='active' DESC,name", params).fetchall()
    return [row_dict(row) for row in rows]


@app.post("/api/appointment-services", status_code=status.HTTP_201_CREATED)
def create_appointment_service(data: AppointmentServiceInput,
                               user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    with connection() as con:
        if data.branch_id is None:
            branches = con.execute("SELECT id FROM branches WHERE tenant_id=? AND status='active'", (scope,)).fetchall()
            if not module_enabled(con, scope, "appointments") and not any(
                module_enabled(con, scope, "appointments", branch["id"]) for branch in branches
            ):
                if user["role"] == "super_admin":
                    raise HTTPException(status_code=409, detail="Activa el módulo Agenda de citas en Disponibilidad para el negocio o una sucursal antes de agregar servicios.")
                raise HTTPException(status_code=404, detail="Recurso no encontrado")
        else:
            if not module_enabled(con, scope, "appointments", data.branch_id):
                if user["role"] == "super_admin":
                    require_module(con, scope, "appointments", data.branch_id)
                raise HTTPException(status_code=404, detail="Recurso no encontrado")
        if data.branch_id and not con.execute(
            "SELECT 1 FROM branches WHERE id=? AND tenant_id=? AND status='active'",
            (data.branch_id, scope),
        ).fetchone():
            raise HTTPException(status_code=422, detail="Sucursal inválida")
        try:
            cur = con.execute(
                """INSERT INTO appointment_services
                (tenant_id,branch_id,name,duration_minutes,price) VALUES (?,?,?,?,?)""",
                (scope, data.branch_id, data.name.strip(), data.duration_minutes, data.price),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Ya existe un servicio con ese nombre")
        audit(con, user, "create", "appointment_service", cur.lastrowid, data.model_dump())
        created = con.execute("SELECT * FROM appointment_services WHERE id=?", (cur.lastrowid,)).fetchone()
    return row_dict(created)


@app.put("/api/appointment-services/{service_id}/status")
def appointment_service_status(service_id: int, data: AppointmentServiceStatusInput,
                               user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        service = con.execute("SELECT * FROM appointment_services WHERE id=?", (service_id,)).fetchone()
        if not service:
            raise HTTPException(status_code=404, detail="Servicio no encontrado")
        tenant_scope(user, service["tenant_id"])
        require_user_module(con, user, "appointments", service["branch_id"])
        new_status = "active" if data.active else "inactive"
        con.execute("UPDATE appointment_services SET status=? WHERE id=?", (new_status, service_id))
        audit(con, user, new_status, "appointment_service", service_id)
    return {"status": new_status}


@app.get("/api/public/{slug}/appointment-services")
def public_appointment_services(slug: str, branch_id: int):
    with connection() as con:
        tenant = con.execute("SELECT * FROM tenants WHERE slug=? AND status='active'", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        require_public_module(con, tenant["id"], "public_page", branch_id)
        require_public_module(con, tenant["id"], "appointments", branch_id)
        rows = con.execute(
            """SELECT id,name,duration_minutes,price,branch_id FROM appointment_services
            WHERE tenant_id=? AND status='active' AND (branch_id IS NULL OR branch_id=?) ORDER BY name""",
            (tenant["id"], branch_id),
        ).fetchall()
    return [row_dict(row) for row in rows]


def appointment_slots_for_day(con, tenant_id, branch_id, service, zone, target_day,
                              stop_at_first=False):
    branch = con.execute("SELECT schedule_mode FROM branches WHERE id=? AND tenant_id=?",
                         (branch_id, tenant_id)).fetchone()
    hours_branch = branch_id if branch["schedule_mode"] == "custom" else None
    hours = con.execute("""SELECT weekday,enabled,opens_at,closes_at FROM business_hours
        WHERE tenant_id=? AND branch_id IS ?""", (tenant_id, hours_branch)).fetchall()
    day_begin = datetime(target_day.year, target_day.month, target_day.day, tzinfo=zone).astimezone(timezone.utc)
    day_end = day_begin + timedelta(days=2)
    occupied = con.execute("""SELECT starts_at,COALESCE(estimated_end_at,ends_at) occupied_end
        FROM appointments WHERE tenant_id=? AND branch_id=? AND status IN ('scheduled','confirmed')
        AND starts_at<? AND COALESCE(estimated_end_at,ends_at)>?""",
        (tenant_id, branch_id, day_end.isoformat(), day_begin.isoformat())).fetchall()
    busy = [(datetime.fromisoformat(row["starts_at"]), datetime.fromisoformat(row["occupied_end"]))
            for row in occupied]
    now = datetime.now(timezone.utc) + timedelta(minutes=10)
    result = []
    for hour in range(24):
        for minute in (0, 30):
            local = datetime(target_day.year, target_day.month, target_day.day,
                             hour, minute, tzinfo=zone)
            starts = local.astimezone(timezone.utc)
            if starts.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
                continue
            ends = starts + timedelta(minutes=service["duration_minutes"])
            if starts < now or not (_hours_open(hours, local) and
                                   _hours_open(hours, (ends - timedelta(minutes=1)).astimezone(zone))):
                continue
            available = not any(begin < ends and finish > starts for begin, finish in busy)
            result.append({"time": f"{hour:02d}:{minute:02d}",
                           "starts_at": starts.isoformat(), "available": available})
            if available and stop_at_first:
                return result
    return result


@app.get("/api/public/{slug}/appointment-availability")
def appointment_availability(slug: str, branch_id: int, service_id: int, date: str):
    selected = date
    try:
        day = datetime.strptime(selected, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Escoge una fecha válida")
    with connection() as con:
        tenant = con.execute("SELECT * FROM tenants WHERE slug=? AND status='active'", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        branch = con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=? AND status='active'", (branch_id, tenant["id"])).fetchone()
        if not branch:
            raise HTTPException(status_code=404, detail="Sucursal no disponible")
        require_public_module(con, tenant["id"], "public_page", branch_id)
        require_public_module(con, tenant["id"], "appointments", branch_id)
        service = con.execute("""SELECT * FROM appointment_services WHERE id=? AND tenant_id=? AND status='active'
            AND (branch_id IS NULL OR branch_id=?)""", (service_id, tenant["id"], branch_id)).fetchone()
        if not service:
            raise HTTPException(status_code=404, detail="Servicio no disponible")
        try:
            zone = ZoneInfo(tenant["timezone"])
        except ZoneInfoNotFoundError:
            zone = timezone(timedelta(hours=-5))
        today = datetime.now(zone).date()
        if day < today or day > today + timedelta(days=180):
            raise HTTPException(status_code=422, detail="Escoge una fecha dentro de los próximos 180 días")
        slots = appointment_slots_for_day(con, tenant["id"], branch_id, service, zone, day)
        next_date = None
        if not any(slot["available"] for slot in slots):
            for offset in range(1, 31):
                future = day + timedelta(days=offset)
                if future > today + timedelta(days=180):
                    break
                if any(slot["available"] for slot in appointment_slots_for_day(con, tenant["id"], branch_id, service, zone, future, stop_at_first=True)):
                    next_date = future.isoformat()
                    break
    return {"date": selected, "timezone": tenant["timezone"], "slots": slots,
            "next_available_date": next_date}


@app.get("/api/public/{slug}/appointment-calendar")
def appointment_month_calendar(slug: str, branch_id: int, service_id: int, month: str):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(status_code=422, detail="Mes no válido")
    first = datetime.strptime(month, "%Y-%m").date()
    with connection() as con:
        tenant = con.execute("SELECT * FROM tenants WHERE slug=? AND status='active'", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        if not con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=? AND status='active'",
                           (branch_id, tenant["id"])).fetchone():
            raise HTTPException(status_code=404, detail="Sucursal no disponible")
        require_public_module(con, tenant["id"], "public_page", branch_id)
        require_public_module(con, tenant["id"], "appointments", branch_id)
        service = con.execute("""SELECT * FROM appointment_services WHERE id=? AND tenant_id=?
            AND status='active' AND (branch_id IS NULL OR branch_id=?)""",
            (service_id, tenant["id"], branch_id)).fetchone()
        if not service:
            raise HTTPException(status_code=404, detail="Servicio no disponible")
        try:
            zone = ZoneInfo(tenant["timezone"])
        except ZoneInfoNotFoundError:
            zone = timezone(timedelta(hours=-5))
        today = datetime.now(zone).date()
        if first > today + timedelta(days=180) or first.month < 1:
            raise HTTPException(status_code=422, detail="Mes fuera del período de reservas")
        following = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        days = {}
        day = first
        while day < following:
            if today <= day <= today + timedelta(days=180):
                count = sum(slot["available"] for slot in appointment_slots_for_day(
                    con, tenant["id"], branch_id, service, zone, day))
                if count:
                    days[day.isoformat()] = count
            day += timedelta(days=1)
    return {"month": month, "timezone": tenant["timezone"], "days": days}


@app.post("/api/public/me/appointments", status_code=status.HTTP_201_CREATED)
def book_appointment(data: AppointmentBookingInput, customer=Depends(current_customer)):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        tenant = con.execute("SELECT * FROM tenants WHERE id=? AND status='active'", (customer["tenant_id"],)).fetchone()
        branch = con.execute(
            "SELECT * FROM branches WHERE id=? AND tenant_id=? AND status='active'",
            (data.branch_id, customer["tenant_id"]),
        ).fetchone()
        if not branch:
            raise HTTPException(status_code=422, detail="Sucursal no disponible")
        require_public_module(con, customer["tenant_id"], "public_page", data.branch_id)
        require_public_module(con, customer["tenant_id"], "appointments", data.branch_id)
        service = con.execute(
            """SELECT * FROM appointment_services WHERE id=? AND tenant_id=? AND status='active'
            AND (branch_id IS NULL OR branch_id=?)""",
            (data.service_id, customer["tenant_id"], data.branch_id),
        ).fetchone()
        if not service:
            raise HTTPException(status_code=404, detail="Servicio no disponible")
        starts = parse_appointment_time(data.starts_at, tenant["timezone"])
        ends = starts + timedelta(minutes=service["duration_minutes"])
        if starts < datetime.now(timezone.utc) + timedelta(minutes=10):
            raise HTTPException(status_code=409, detail="La cita debe programarse con al menos 10 minutos de anticipación")
        if not appointment_fits_hours(con, customer["tenant_id"], data.branch_id, starts, ends):
            raise HTTPException(status_code=409, detail="La hora seleccionada está fuera del horario de atención")
        overlap = con.execute(
            """SELECT 1 FROM appointments WHERE branch_id=? AND status IN ('scheduled','confirmed')
            AND starts_at < ? AND COALESCE(estimated_end_at,ends_at) > ? LIMIT 1""",
            (data.branch_id, ends.isoformat(), starts.isoformat()),
        ).fetchone()
        if overlap:
            raise HTTPException(status_code=409, detail="Ese horario ya está ocupado. Elige otra hora.")
        cur = con.execute(
            """INSERT INTO appointments
            (tenant_id,branch_id,customer_id,service_id,starts_at,ends_at,notes)
            VALUES (?,?,?,?,?,?,?)""",
            (customer["tenant_id"], data.branch_id, customer["id"], data.service_id,
             starts.isoformat(), ends.isoformat(), data.notes),
        )
        add_notification(
            con, customer["tenant_id"], data.branch_id, customer["id"], "appointment",
            "Nueva cita agendada",
            f"{customer['name']} agendó {service['name']} en {branch['name']}.",
        )
        created = con.execute(
            """SELECT a.*,s.name service_name,b.name branch_name FROM appointments a
            JOIN appointment_services s ON s.id=a.service_id JOIN branches b ON b.id=a.branch_id
            WHERE a.id=?""", (cur.lastrowid,),
        ).fetchone()
    return row_dict(created)


@app.get("/api/public/me/appointments")
def my_appointments(customer=Depends(current_customer)):
    with connection() as con:
        require_public_module(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id"))
        if not module_enabled(con, customer["tenant_id"], "appointments", customer.get("origin_branch_id")):
            return []
        rows = con.execute(
            """SELECT a.*,s.name service_name,s.duration_minutes,b.name branch_name,b.city,
            t.timezone tenant_timezone
            FROM appointments a JOIN appointment_services s ON s.id=a.service_id
            JOIN branches b ON b.id=a.branch_id JOIN tenants t ON t.id=a.tenant_id
            WHERE a.customer_id=? AND a.tenant_id=?
            ORDER BY a.starts_at DESC LIMIT 100""", (customer["id"], customer["tenant_id"]),
        ).fetchall()
    return [row_dict(row) for row in rows]


@app.post("/api/public/me/appointments/{appointment_id}/cancel")
def cancel_customer_appointment(appointment_id: int, data: AppointmentCancelInput,
                                customer=Depends(current_customer)):
    reason = data.reason.strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Escribe un motivo de al menos cinco caracteres")
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        appointment = con.execute("""SELECT a.*,s.name service_name,b.name branch_name FROM appointments a
            JOIN appointment_services s ON s.id=a.service_id JOIN branches b ON b.id=a.branch_id
            WHERE a.id=? AND a.customer_id=? AND a.tenant_id=?""",
            (appointment_id, customer["id"], customer["tenant_id"])).fetchone()
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada en tu cuenta")
        require_public_module(con, customer["tenant_id"], "public_page", appointment["branch_id"])
        require_public_module(con, customer["tenant_id"], "appointments", appointment["branch_id"])
        if appointment["status"] not in ("scheduled", "confirmed"):
            raise HTTPException(status_code=409, detail="Esta cita ya no puede cancelarse")
        if datetime.fromisoformat(appointment["starts_at"]) <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="No es posible cancelar una cita que ya comenzó")
        con.execute("""UPDATE appointments SET status='cancelled',cancellation_reason=?,
            cancelled_at=?,cancelled_by='customer',updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (reason, datetime.now(timezone.utc).isoformat(), appointment_id))
        add_notification(con, customer["tenant_id"], appointment["branch_id"], customer["id"],
                         "appointment_cancelled", "Cita cancelada por el cliente",
                         f"{customer['name']} canceló {appointment['service_name']} en {appointment['branch_name']}. Motivo: {reason}")
    return {"status": "cancelled", "cancellation_reason": reason}


@app.get("/api/appointments")
def list_appointments(tenant_id: int | None = None, branch_id: int | None = None,
                      month: str | None = None,
                      user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    if user["role"] == "branch_admin":
        branch_id = user["branch_id"]
    with connection() as con:
        require_user_module(con, user, "appointments", branch_id)
        query = """SELECT a.*,c.name customer_name,c.phone customer_phone,s.name service_name,s.duration_minutes,
        b.name branch_name,t.timezone tenant_timezone FROM appointments a JOIN customers c ON c.id=a.customer_id
        JOIN appointment_services s ON s.id=a.service_id JOIN branches b ON b.id=a.branch_id
        JOIN tenants t ON t.id=a.tenant_id
        WHERE a.tenant_id=?"""
        params = [scope]
        if branch_id is not None:
            query += " AND a.branch_id=?"
            params.append(branch_id)
        if month:
            try:
                if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
                    raise ValueError()
                first = datetime.strptime(month, "%Y-%m")
            except ValueError:
                raise HTTPException(status_code=422, detail="Mes no válido")
            zone_name = con.execute("SELECT timezone FROM tenants WHERE id=?", (scope,)).fetchone()["timezone"]
            try:
                zone = ZoneInfo(zone_name)
            except ZoneInfoNotFoundError:
                zone = timezone(timedelta(hours=-5))
            following = datetime(first.year + (first.month == 12), first.month % 12 + 1, 1)
            query += " AND a.starts_at>=? AND a.starts_at<?"
            params.extend([first.replace(tzinfo=zone).astimezone(timezone.utc).isoformat(),
                           following.replace(tzinfo=zone).astimezone(timezone.utc).isoformat()])
        rows = con.execute(query + f" ORDER BY a.starts_at DESC LIMIT {2000 if month else 500}", params).fetchall()
    return [row_dict(row) for row in rows]


@app.get("/api/worker/appointments")
def worker_appointments(user=Depends(require("worker", "branch_admin"))):
    if not user["tenant_id"] or not user["branch_id"]:
        raise HTTPException(status_code=403, detail="Tu cuenta necesita una sucursal asignada")
    with connection() as con:
        require_user_module(con, user, "appointments", user["branch_id"])
        tenant = con.execute("SELECT timezone FROM tenants WHERE id=?", (user["tenant_id"],)).fetchone()
        try:
            zone = ZoneInfo(tenant["timezone"])
        except ZoneInfoNotFoundError:
            zone = timezone(timedelta(hours=-5))
        today = datetime.now(zone).date()
        begin = datetime(today.year, today.month, today.day, tzinfo=zone).astimezone(timezone.utc)
        after_tomorrow = today + timedelta(days=2)
        end = datetime(after_tomorrow.year, after_tomorrow.month, after_tomorrow.day,
                       tzinfo=zone).astimezone(timezone.utc)
        rows = con.execute("""SELECT a.id,a.starts_at,a.ends_at,a.estimated_end_at,a.delay_minutes,
            a.status,c.name customer_name,s.name service_name,s.duration_minutes,t.timezone tenant_timezone
            FROM appointments a JOIN customers c ON c.id=a.customer_id
            JOIN appointment_services s ON s.id=a.service_id JOIN tenants t ON t.id=a.tenant_id
            WHERE a.tenant_id=? AND a.branch_id=? AND a.status IN ('scheduled','confirmed')
            AND a.starts_at>=? AND a.starts_at<? ORDER BY a.starts_at LIMIT 100""",
            (user["tenant_id"], user["branch_id"], begin.isoformat(), end.isoformat())).fetchall()
    return [row_dict(row) for row in rows]


@app.put("/api/appointments/{appointment_id}/status")
def update_appointment_status(appointment_id: int, data: AppointmentStatusInput,
                              user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    with connection() as con:
        appointment = con.execute("SELECT * FROM appointments WHERE id=?", (appointment_id,)).fetchone()
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        tenant_scope(user, appointment["tenant_id"])
        require_user_module(con, user, "appointments", appointment["branch_id"])
        if user["role"] == "branch_admin" and appointment["branch_id"] != user["branch_id"]:
            raise HTTPException(status_code=403, detail="Cita fuera de su sucursal")
        if appointment["status"] not in ("scheduled", "confirmed"):
            raise HTTPException(status_code=409, detail="Esta cita ya terminó o fue cancelada")
        con.execute(
            """UPDATE appointments SET status=?,updated_at=CURRENT_TIMESTAMP,
            cancelled_at=CASE WHEN ?='cancelled' THEN ? ELSE cancelled_at END,
            cancelled_by=CASE WHEN ?='cancelled' THEN 'business' ELSE cancelled_by END WHERE id=?""",
            (data.status, data.status, datetime.now(timezone.utc).isoformat(), data.status, appointment_id),
        )
        audit(con, user, data.status, "appointment", appointment_id)
        if data.status == "cancelled":
            add_notification(con, appointment["tenant_id"], appointment["branch_id"], appointment["customer_id"],
                             "appointment_cancelled", "Cita cancelada por el negocio",
                             "La cita fue cancelada por el negocio. Consulta la agenda para reservar otra hora.")
    return {"status": data.status}


@app.post("/api/appointments/{appointment_id}/delay")
def report_appointment_delay(appointment_id: int, data: AppointmentDelayInput,
                             user=Depends(require("super_admin", "business_admin", "branch_admin", "worker"))):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        appointment = con.execute("""SELECT a.*,s.name service_name,b.name branch_name,
            t.timezone tenant_timezone FROM appointments a
            JOIN appointment_services s ON s.id=a.service_id JOIN branches b ON b.id=a.branch_id
            JOIN tenants t ON t.id=a.tenant_id WHERE a.id=?""", (appointment_id,)).fetchone()
        if not appointment:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        require_user_module(con, user, "appointments", appointment["branch_id"])
        if user["role"] == "super_admin":
            pass
        elif user["tenant_id"] != appointment["tenant_id"] or (
            user["role"] in ("worker", "branch_admin") and user["branch_id"] != appointment["branch_id"]
        ):
            raise HTTPException(status_code=403, detail="Cita fuera de tu negocio o sucursal")
        if appointment["status"] not in ("scheduled", "confirmed"):
            raise HTTPException(status_code=409, detail="Solo se puede registrar demora en una cita activa")
        end = datetime.fromisoformat(appointment["ends_at"])
        estimated = (end + timedelta(minutes=data.delay_minutes)).isoformat() if data.delay_minutes else None
        note = (data.reason or "").strip() or None
        con.execute("""UPDATE appointments SET delay_minutes=?,delay_reason=?,estimated_end_at=?,
            updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (data.delay_minutes, note, estimated, appointment_id))
        affected = []
        if estimated:
            affected = con.execute("""SELECT id,customer_id FROM appointments
                WHERE tenant_id=? AND branch_id=? AND id<>? AND status IN ('scheduled','confirmed')
                AND starts_at < ? AND ends_at > ? ORDER BY starts_at""",
                (appointment["tenant_id"], appointment["branch_id"], appointment_id,
                 estimated, appointment["ends_at"])).fetchall()
        if data.delay_minutes != appointment["delay_minutes"]:
            try:
                zone = ZoneInfo(appointment["tenant_timezone"])
            except ZoneInfoNotFoundError:
                zone = timezone(timedelta(hours=-5))
            local_end = (end + timedelta(minutes=data.delay_minutes)).astimezone(zone)
            local_time = f"{local_end.hour % 12 or 12}:{local_end.minute:02d} {'a. m.' if local_end.hour < 12 else 'p. m.'}"
            if data.delay_minutes:
                add_notification(con, appointment["tenant_id"], appointment["branch_id"],
                                 appointment["customer_id"], "appointment_delay", "Demora en tu cita",
                                 f"{appointment['service_name']} presenta una demora aproximada de {data.delay_minutes} minutos. Finalización estimada: {local_time}.")
                for row in affected:
                    add_notification(con, appointment["tenant_id"], appointment["branch_id"],
                                     row["customer_id"], "appointment_delay", "Posible demora en tu cita",
                                     "Una cita anterior se prolongó. El negocio te confirmará si cambia tu hora de atención.")
        audit(con, user, "delay", "appointment", appointment_id,
              {"delay_minutes": data.delay_minutes, "affected": len(affected)})
    return {"delay_minutes": data.delay_minutes, "estimated_end_at": estimated,
            "affected_count": len(affected)}


@app.get("/api/notifications/stream")
def notification_stream(after_id: int | None = None,
                        user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    with connection() as con:
        require_user_module(con, user, "notifications")
    query = """SELECT n.id,n.title,n.message,n.event_type,n.image_url,t.name business_name
        FROM notifications n JOIN tenants t ON t.id=n.tenant_id WHERE 1=1"""
    params = []
    if user["role"] != "super_admin":
        query += " AND n.tenant_id=?"
        params.append(user["tenant_id"])
    if user["role"] == "branch_admin":
        query += " AND n.branch_id=?"
        params.append(user["branch_id"])
    with connection() as con:
        if after_id is None:
            latest = con.execute(
                query.replace(
                    "SELECT n.id,n.title,n.message,n.event_type,t.name business_name",
                    "SELECT MAX(n.id) latest",
                ),
                params,
            ).fetchone()["latest"] or 0
            return {"last_id": latest, "items": []}
        rows = con.execute(query + " AND n.id>? ORDER BY n.id LIMIT 30", (*params, max(0, after_id))).fetchall()
    return {"last_id": rows[-1]["id"] if rows else after_id, "items": [row_dict(row) for row in rows]}


@app.get("/api/public/me/notifications")
def customer_notification_stream(after_id: int | None = None, customer=Depends(current_customer)):
    with connection() as con:
        if not module_enabled(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id")):
            return {"last_id": after_id or 0, "items": []}
        if not module_enabled(con, customer["tenant_id"], "notifications", customer.get("origin_branch_id")):
            return {"last_id": after_id or 0, "items": []}
        if after_id is None:
            latest = con.execute("SELECT MAX(id) latest FROM notifications WHERE tenant_id=? AND customer_id=?",
                                 (customer["tenant_id"], customer["id"])).fetchone()["latest"] or 0
            return {"last_id": latest, "items": []}
        rows = con.execute("""SELECT id,title,message,event_type,image_url FROM notifications
            WHERE tenant_id=? AND customer_id=? AND id>? ORDER BY id LIMIT 30""",
            (customer["tenant_id"], customer["id"], max(0, after_id))).fetchall()
    return {"last_id": rows[-1]["id"] if rows else after_id, "items": [row_dict(row) for row in rows]}

@app.get("/api/public/{slug}/push-config")
def public_push_config(slug: str):
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
        if not tenant:
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        key = con.execute("SELECT public_key FROM push_keys WHERE id=1").fetchone()
    return {"public_key": key["public_key"] if key else None}

@app.post("/api/public/me/push-subscription")
def save_push_subscription(data: PushSubscriptionInput, customer=Depends(current_customer)):
    with connection() as con:
        con.execute("""INSERT INTO push_subscriptions(customer_id,tenant_id,endpoint,p256dh,auth,updated_at)
            VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(endpoint) DO UPDATE SET customer_id=excluded.customer_id,tenant_id=excluded.tenant_id,
            p256dh=excluded.p256dh,auth=excluded.auth,updated_at=CURRENT_TIMESTAMP""",
            (customer["id"], customer["tenant_id"], data.endpoint, data.p256dh, data.auth))
    return {"saved": True}

@app.delete("/api/public/me/push-subscription")
def delete_push_subscription(data: PushSubscriptionInput, customer=Depends(current_customer)):
    with connection() as con:
        con.execute("DELETE FROM push_subscriptions WHERE endpoint=? AND customer_id=?", (data.endpoint, customer["id"]))
    return {"deleted": True}


@app.get("/api/notifications")
def list_notifications(tenant_id: int | None = None,
                       user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "notifications")
        query = """SELECT n.*,b.name branch_name,c.name customer_name FROM notifications n
        LEFT JOIN branches b ON b.id=n.branch_id LEFT JOIN customers c ON c.id=n.customer_id
        WHERE n.tenant_id=?"""
        params = [scope]
        if user["role"] == "branch_admin":
            query += " AND n.branch_id=?"
            params.append(user["branch_id"])
        rows = con.execute(query + " ORDER BY n.id DESC LIMIT 200", params).fetchall()
        unread = sum(1 for row in rows if not row["read_at"])
    return {"unread": unread, "items": [row_dict(row) for row in rows]}


@app.post("/api/notifications/send")
def send_notification(data: NotificationSendInput,
                      user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    branch_id = data.branch_id or (user.get("branch_id") if user["role"] == "branch_admin" else None)
    image_url = data.image_url.strip() if data.image_url else None
    if image_url:
        match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", image_url)
        if not match:
            raise HTTPException(status_code=422, detail="La imagen debe ser PNG, JPG o WebP")
        if len(match.group(2)) > 1_800_000:
            raise HTTPException(status_code=413, detail="La imagen debe pesar máximo 1.3 MB")
    with connection() as con:
        require_user_module(con, user, "notifications")
        if branch_id and not con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=? AND status='active'", (branch_id, scope)).fetchone():
            raise HTTPException(status_code=422, detail="Sucursal inválida")
        query = "SELECT c.id FROM customers c WHERE c.tenant_id=? AND c.status='active'"
        params: list = [scope]
        if branch_id:
            query += " AND c.origin_branch_id=?"; params.append(branch_id)
        if data.audience == "selected":
            ids = sorted({int(x) for x in data.customer_ids})
            if not ids:
                raise HTTPException(status_code=422, detail="Selecciona al menos un cliente")
            marks = ",".join("?" for _ in ids); query += f" AND c.id IN ({marks})"; params.extend(ids)
        elif data.audience == "loyal":
            query = "SELECT c.id FROM customers c LEFT JOIN purchases p ON p.customer_id=c.id AND p.tenant_id=? WHERE c.tenant_id=? AND c.status='active'"
            params = [scope, scope]
            if branch_id:
                query += " AND c.origin_branch_id=?"; params.append(branch_id)
            query += " GROUP BY c.id ORDER BY COUNT(p.id) DESC, c.created_at ASC LIMIT 20"
        recipients = con.execute(query, params).fetchall()
        push_sent = 0
        for row in recipients:
            add_notification(con, scope, branch_id, row["id"], "broadcast", data.title.strip(), data.message.strip(), image_url)
            if send_push_notification(con, row["id"], data.title.strip(), data.message.strip()):
                push_sent += 1
    return {"sent": len(recipients), "push_sent": push_sent, "audience": data.audience}

def collaboration_image(value: str | None):
    if not value:
        return None
    value = value.strip()
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", value)
    if not match or len(match.group(2)) > 1_800_000:
        raise HTTPException(status_code=422, detail="La imagen debe ser PNG, JPG o WebP y pesar máximo 1.3 MB")
    return value

def collaboration_end(value: str | None):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=422, detail="La fecha final de la colaboración no es válida")
    return parsed.isoformat()

def collaboration_expired(value: str | None):
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("America/Bogota"))
        return parsed <= datetime.now(parsed.tzinfo)
    except (ValueError, ZoneInfoNotFoundError):
        return False

def collaboration_scope(row, user):
    if user["role"] == "super_admin":
        return row["requester_tenant_id"]
    scope = user.get("tenant_id")
    if scope not in (row["requester_tenant_id"], row["partner_tenant_id"]):
        raise HTTPException(status_code=403, detail="Colaboración fuera de su alcance")
    return scope

@app.get("/api/collaborations/contacts")
def collaboration_contacts(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "collaborations")
        rows = con.execute("""SELECT t.id,t.name,t.slug,c.whatsapp,bb.display_name,bb.welcome_text,
            CASE WHEN bb.logo_mime IS NOT NULL THEN '/api/public/branding/'||t.id||'/logo' ELSE NULL END logo_url
            FROM tenants t
            LEFT JOIN collaboration_contacts c ON c.tenant_id=t.id
            LEFT JOIN business_branding bb ON bb.tenant_id=t.id
            WHERE t.status='active' AND t.deleted_at IS NULL AND t.id<>? AND COALESCE(c.visible,0)=1 ORDER BY t.name COLLATE NOCASE""", (scope,)).fetchall()
    return [row_dict(row) for row in rows]

@app.get("/api/collaborations/contact")
def collaboration_contact(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "collaborations")
        row = con.execute("SELECT tenant_id,whatsapp,visible FROM collaboration_contacts WHERE tenant_id=?", (scope,)).fetchone()
    return row_dict(row) if row else {"tenant_id": scope, "whatsapp": "", "visible": False}

@app.get("/api/collaborations")
def list_collaborations(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "collaborations")
        rows = con.execute("""SELECT c.*,a.name requester_name,b.name partner_name,
            ca.whatsapp requester_whatsapp,cb.whatsapp partner_whatsapp
            FROM collaborations c JOIN tenants a ON a.id=c.requester_tenant_id JOIN tenants b ON b.id=c.partner_tenant_id
            LEFT JOIN collaboration_contacts ca ON ca.tenant_id=a.id LEFT JOIN collaboration_contacts cb ON cb.tenant_id=b.id
            WHERE c.requester_tenant_id=? OR c.partner_tenant_id=? ORDER BY c.id DESC""", (scope, scope)).fetchall()
    return [row_dict(row) for row in rows]

@app.put("/api/collaborations/contact")
def save_collaboration_contact(data: CollaborationContactInput, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    with connection() as con:
        require_user_module(con, user, "collaborations")
        con.execute("""INSERT INTO collaboration_contacts(tenant_id,whatsapp,visible,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(tenant_id) DO UPDATE SET whatsapp=excluded.whatsapp,visible=excluded.visible,updated_at=CURRENT_TIMESTAMP""",
            (scope, data.whatsapp.strip(), int(data.visible)))
    return {"saved": True}

@app.post("/api/collaborations")
def create_collaboration(data: CollaborationCreateInput, user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, data.tenant_id)
    if data.partner_tenant_id == scope:
        raise HTTPException(status_code=422, detail="Escoge otro negocio")
    image_url = collaboration_image(data.image_url)
    with connection() as con:
        require_user_module(con, user, "collaborations")
        partner = con.execute("SELECT id FROM tenants WHERE id=? AND status='active' AND deleted_at IS NULL", (data.partner_tenant_id,)).fetchone()
        contact = con.execute("SELECT 1 FROM collaboration_contacts WHERE tenant_id=? AND visible=1", (data.partner_tenant_id,)).fetchone()
        if not partner or not contact:
            raise HTTPException(status_code=422, detail="Ese negocio no está disponible para colaboraciones")
        cur = con.execute("""INSERT INTO collaborations(requester_tenant_id,partner_tenant_id,title,message,image_url,ends_at,ad_seconds,is_active)
            VALUES(?,?,?,?,?,?,?,1)""", (scope, data.partner_tenant_id, data.title.strip(), data.message.strip(), image_url, collaboration_end(data.ends_at), data.ad_seconds))
    return {"id": cur.lastrowid, "status": "pending"}

@app.put("/api/collaborations/{collaboration_id}")
def edit_collaboration(collaboration_id: int, data: CollaborationUpdateInput, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        row = con.execute("SELECT * FROM collaborations WHERE id=?", (collaboration_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Colaboración no encontrada")
        scope = collaboration_scope(row, user)
        require_user_module(con, user, "collaborations")
        image_url = collaboration_image(data.image_url) if data.image_url else row["image_url"]
        con.execute("""UPDATE collaborations SET title=?,message=?,image_url=?,ends_at=?,ad_seconds=?,updated_at=CURRENT_TIMESTAMP
            WHERE id=?""", (data.title.strip(), data.message.strip(), image_url, collaboration_end(data.ends_at), data.ad_seconds, collaboration_id))
    return {"saved": True, "id": collaboration_id, "tenant_id": scope}

@app.delete("/api/collaborations/{collaboration_id}")
def delete_collaboration(collaboration_id: int, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        row = con.execute("SELECT * FROM collaborations WHERE id=?", (collaboration_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Colaboración no encontrada")
        collaboration_scope(row, user)
        require_user_module(con, user, "collaborations")
        con.execute("DELETE FROM collaborations WHERE id=?", (collaboration_id,))
    return {"deleted": True}

@app.put("/api/collaborations/{collaboration_id}/active")
def set_collaboration_active(collaboration_id: int, data: CollaborationActiveInput, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        row = con.execute("SELECT * FROM collaborations WHERE id=?", (collaboration_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Colaboración no encontrada")
        collaboration_scope(row, user)
        require_user_module(con, user, "collaborations")
        con.execute("UPDATE collaborations SET is_active=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (int(data.active), collaboration_id))
    return {"active": data.active}

@app.put("/api/collaborations/{collaboration_id}/status")
def update_collaboration_status(collaboration_id: int, data: CollaborationStatusInput, user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        row = con.execute("SELECT * FROM collaborations WHERE id=?", (collaboration_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Colaboración no encontrada")
        scope = collaboration_scope(row, user)
        require_user_module(con, user, "collaborations")
        field = "requester_status" if scope == row["requester_tenant_id"] else "partner_status"
        con.execute(f"UPDATE collaborations SET {field}=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (data.status, collaboration_id))
        updated = con.execute("SELECT requester_status,partner_status FROM collaborations WHERE id=?", (collaboration_id,)).fetchone()
        final = "active" if updated["requester_status"] == "accepted" and updated["partner_status"] == "accepted" else data.status
    return {"status": final}

@app.get("/api/public/{slug}/collaborations")
def public_collaborations(slug: str):
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
        if not tenant or not module_enabled(con, tenant["id"], "public_page") or not module_enabled(con, tenant["id"], "collaborations"):
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        rows = con.execute("""SELECT c.id,c.title,c.message,c.image_url,c.created_at,c.ends_at,c.ad_seconds,c.is_active,
            CASE WHEN c.requester_tenant_id=? THEN b.name ELSE a.name END partner_name
            FROM collaborations c JOIN tenants a ON a.id=c.requester_tenant_id JOIN tenants b ON b.id=c.partner_tenant_id
            WHERE (c.requester_tenant_id=? OR c.partner_tenant_id=?) AND c.requester_status='accepted' AND c.partner_status='accepted' AND c.is_active=1""",
            (tenant["id"], tenant["id"], tenant["id"])).fetchall()
    return [row_dict(row) for row in rows if not collaboration_expired(row["ends_at"])]


@app.get("/api/public/{slug}/platform-ads")
def public_platform_ads(slug: str):
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with connection() as con:
        tenant = con.execute("SELECT id FROM tenants WHERE slug=? AND status='active' AND deleted_at IS NULL", (slug,)).fetchone()
        if not tenant or not module_enabled(con, tenant["id"], "public_page"):
            raise HTTPException(status_code=404, detail="Negocio no encontrado")
        rows = con.execute("""SELECT id,title,message,image_url,target_tenants_json,starts_at,ends_at,ad_seconds
            FROM platform_ads WHERE is_active=1
            AND (starts_at IS NULL OR starts_at<=?)
            AND (ends_at IS NULL OR ends_at>=?)
            ORDER BY created_at DESC,id DESC""", (now, now)).fetchall()
    result = []
    for row in rows:
        try:
            targets = json.loads(row["target_tenants_json"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            targets = []
        if not targets or tenant["id"] in targets:
            result.append(row_dict(row))
    with connection() as con:
        business_rows = con.execute("""SELECT id,title,message,image_url,starts_at,ends_at,ad_seconds
            FROM business_ads WHERE tenant_id=? AND is_active=1
            AND (starts_at IS NULL OR starts_at<=?)
            AND (ends_at IS NULL OR ends_at>=?)
            ORDER BY created_at DESC,id DESC""", (tenant["id"], now, now)).fetchall()
    result.extend([{**row_dict(row), "source": "business"} for row in business_rows])
    return result

@app.post("/api/notifications/read-all")
def read_all_notifications(tenant_id: int | None = None,
                           user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    scope = tenant_scope(user, tenant_id)
    with connection() as con:
        require_user_module(con, user, "notifications")
        if user["role"] == "branch_admin":
            cur = con.execute(
                "UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND branch_id=? AND read_at IS NULL",
                (scope, user["branch_id"]),
            )
        else:
            cur = con.execute(
                "UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND read_at IS NULL",
                (scope,),
            )
    return {"status": "read", "count": cur.rowcount}


def time_view(con,i):
    r=con.execute("""SELECT s.*,ts.name service_name,ts.duration_minutes,b.name branch_name,c.name customer_name,c.phone customer_phone,u.name worker_name FROM time_sessions s JOIN time_services ts ON ts.id=s.service_id JOIN branches b ON b.id=s.branch_id JOIN customers c ON c.id=s.customer_id JOIN users u ON u.id=s.worker_id WHERE s.id=?""",(i,)).fetchone()
    if not r:return None
    item=row_dict(r)
    if item.get("status")=="open":
        try:
            remaining=max(0,ceil((datetime.fromisoformat(item["planned_end_at"])-datetime.now(timezone.utc)).total_seconds()/60))
        except (TypeError,ValueError):
            remaining=None
        item["remaining_minutes"]=remaining
    else:
        item["remaining_minutes"]=0
    return item

def close_expired_time_sessions(con, tenant_id: int | None = None, customer_id: int | None = None):
    """Close sessions whose planned end has passed and notify the customer once."""
    now = datetime.now(timezone.utc)
    query = """SELECT s.id,s.tenant_id,s.branch_id,s.customer_id,s.started_at,s.planned_end_at,
                     ts.price,ts.duration_minutes,ts.name service_name
                FROM time_sessions s JOIN time_services ts ON ts.id=s.service_id
               WHERE s.status='open' AND s.planned_end_at<=?"""
    params: list = [now.isoformat()]
    if tenant_id is not None:
        query += " AND s.tenant_id=?"; params.append(tenant_id)
    if customer_id is not None:
        query += " AND s.customer_id=?"; params.append(customer_id)
    rows = con.execute(query, params).fetchall()
    for row in rows:
        duration = max(1, int(row["duration_minutes"]))
        con.execute("""UPDATE time_sessions
                       SET status='closed',ended_at=?,minutes_used=?,total_price=?,
                           close_notes=?,closed_by_user_id=NULL
                       WHERE id=? AND status='open'""",
                    (row["planned_end_at"], duration, row["price"],
                     "Tiempo finalizado automáticamente", row["id"]))
        add_notification(con, row["tenant_id"], row["branch_id"], row["customer_id"],
                         "time_expired", "Tiempo finalizado",
                         f"El servicio {row['service_name']} ha terminado.")
    return len(rows)

@app.get("/api/time-services")
def time_services(tenant_id:int|None=None,branch_id:int|None=None,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    scope=tenant_scope(user,tenant_id);branch_id=user["branch_id"] if user["role"] in {"worker","branch_admin"} else branch_id
    with connection() as con:
        require_user_module(con, user, "time_sales", branch_id)
        q,p="SELECT * FROM time_services WHERE tenant_id=?",[scope]
        if branch_id is not None:q+=" AND (branch_id IS NULL OR branch_id=?)";p.append(branch_id)
        return [row_dict(x) for x in con.execute(q+" ORDER BY status='active' DESC,name",p).fetchall()]
@app.post("/api/time-services")
def create_time_service(data:TimeServiceInput,user=Depends(require("super_admin","business_admin"))):
    scope=tenant_scope(user,data.tenant_id)
    with connection() as con:
        if data.branch_id is not None and not con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=? AND status='active'",(data.branch_id,scope)).fetchone():
            raise HTTPException(404,"Sucursal no encontrada para este negocio")
        if not module_enabled(con, scope, "time_sales", data.branch_id):
            if user["role"] == "super_admin":
                require_module(con, scope, "time_sales", data.branch_id)
            raise HTTPException(status_code=404, detail="Recurso no encontrado")
        cur=con.execute("INSERT INTO time_services (tenant_id,branch_id,name,duration_minutes,price) VALUES (?,?,?,?,?)",(scope,data.branch_id,data.name.strip(),data.duration_minutes,data.price));audit(con,user,"create","time_service",cur.lastrowid,{"name":data.name})
    return {"id":cur.lastrowid,"message":"Servicio por tiempo creado"}
@app.put("/api/time-services/{service_id}/status")
def set_time_service(service_id:int,data:TimeServiceStatusInput,user=Depends(require("super_admin","business_admin"))):
    with connection() as con:
        r=con.execute("SELECT * FROM time_services WHERE id=?",(service_id,)).fetchone()
        if not r:raise HTTPException(404,"Servicio no encontrado")
        tenant_scope(user,r["tenant_id"]);require_user_module(con,user,"time_sales",r["branch_id"]);con.execute("UPDATE time_services SET status=? WHERE id=?",("active" if data.active else "inactive",service_id))
    return {"status":"active" if data.active else "inactive"}
@app.get("/api/time-sessions")
def time_sessions(tenant_id:int|None=None,branch_id:int|None=None,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    scope=tenant_scope(user,tenant_id);branch_id=user["branch_id"] if user["role"] in {"worker","branch_admin"} else branch_id
    with connection() as con:
        require_user_module(con, user, "time_sales", branch_id)
        close_expired_time_sessions(con, scope)
        q,p="SELECT id FROM time_sessions WHERE tenant_id=?",[scope]
        if branch_id is not None:q+=" AND branch_id=?";p.append(branch_id)
        return [time_view(con,x["id"]) for x in con.execute(q+" ORDER BY status='open' DESC,started_at DESC LIMIT 300",p).fetchall()]
@app.post("/api/time-sessions")
def start_time_session(data:TimeSessionStartInput,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    scope=tenant_scope(user,data.tenant_id)
    if user["role"] in {"worker","branch_admin"} and user["branch_id"]!=data.branch_id:raise HTTPException(403,"No puedes iniciar sesiones de otra sucursal")
    with connection() as con:
        require_worker_access(con, user, "time_sales")
        if not con.execute("SELECT 1 FROM branches WHERE id=? AND tenant_id=? AND status='active'",(data.branch_id,scope)).fetchone():
            raise HTTPException(404,"Sucursal no encontrada para este negocio")
        if not module_enabled(con, scope, "time_sales", data.branch_id):
            if user["role"] == "super_admin":
                require_module(con, scope, "time_sales", data.branch_id)
            raise HTTPException(status_code=404, detail="Recurso no encontrado")
        close_expired_time_sessions(con, scope, data.customer_id)
        require_service_open(con,scope,data.branch_id);s=con.execute("SELECT * FROM time_services WHERE id=? AND tenant_id=? AND status='active' AND (branch_id IS NULL OR branch_id=?)",(data.service_id,scope,data.branch_id)).fetchone()
        if not s:raise HTTPException(404,"Servicio no disponible para esta sucursal")
        if not con.execute("SELECT 1 FROM customers WHERE id=? AND tenant_id=? AND status='active'",(data.customer_id,scope)).fetchone():raise HTTPException(404,"Cliente no encontrado")
        if con.execute("SELECT 1 FROM time_sessions WHERE customer_id=? AND status='open'",(data.customer_id,)).fetchone():raise HTTPException(409,"Este cliente ya tiene una sesión abierta")
        now=datetime.now(timezone.utc);cur=con.execute("INSERT INTO time_sessions (tenant_id,branch_id,customer_id,service_id,worker_id,started_at,planned_end_at) VALUES (?,?,?,?,?,?,?)",(scope,data.branch_id,data.customer_id,data.service_id,user["id"],now.isoformat(),(now+timedelta(minutes=s["duration_minutes"])).isoformat()))
        return time_view(con,cur.lastrowid)
@app.post("/api/time-sessions/{session_id}/close")
def close_time_session(session_id:int,data:TimeSessionCloseInput,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        r=con.execute("SELECT s.*,ts.price FROM time_sessions s JOIN time_services ts ON ts.id=s.service_id WHERE s.id=?",(session_id,)).fetchone()
        if not r:raise HTTPException(404,"Sesión no encontrada")
        tenant_scope(user,r["tenant_id"])
        require_worker_access(con, user, "time_sales")
        require_user_module(con,user,"time_sales",r["branch_id"])
        if user["role"] in {"worker","branch_admin"} and user["branch_id"]!=r["branch_id"]:raise HTTPException(403,"No puedes cerrar otra sucursal")
        if r["status"]!="open":raise HTTPException(409,"Esta sesión ya fue cerrada")
        end=datetime.now(timezone.utc);mins=max(1,ceil((end-datetime.fromisoformat(r["started_at"])).total_seconds()/60));con.execute("UPDATE time_sessions SET status='closed',ended_at=?,minutes_used=?,total_price=?,close_notes=?,closed_by_user_id=? WHERE id=?",(end.isoformat(),mins,r["price"],data.notes,user["id"],session_id));return time_view(con,session_id)
@app.get("/api/worker/customers")
def worker_time_customers(q:str="",user=Depends(require("worker","branch_admin"))):
    if len(q.strip())<2:return []
    with connection() as con:
        require_user_module(con, user, "time_sales", user.get("branch_id"))
        return [row_dict(x) for x in con.execute("SELECT id,name,phone FROM customers WHERE tenant_id=? AND status='active' AND (name LIKE ? OR phone LIKE ?) LIMIT 25",(user["tenant_id"],f"%{q.strip()}%",f"%{q.strip()}%")).fetchall()]
@app.get("/api/worker/time-sessions")
def worker_time_sessions(user=Depends(require("worker","branch_admin"))):return time_sessions(user["tenant_id"],user["branch_id"],user)

@app.get("/api/public/me/time-sessions")
def customer_time_sessions(customer=Depends(current_customer)):
    with connection() as con:
        if not module_enabled(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id")):
            return []
        if not module_enabled(con, customer["tenant_id"], "time_sales", customer.get("origin_branch_id")):
            return []
        close_expired_time_sessions(con, customer["tenant_id"], customer["id"])
        rows = con.execute("""SELECT id FROM time_sessions
            WHERE tenant_id=? AND customer_id=?
            ORDER BY started_at DESC LIMIT 50""", (customer["tenant_id"], customer["id"])).fetchall()
        return [time_view(con, row["id"]) for row in rows]
@app.post("/api/backups")
def make_backup(user=Depends(require("super_admin"))):
    target = create_backup("manual")
    archive = target.with_suffix(".zip")
    return {"status": "created", "filename": target.name, "size": target.stat().st_size,
            "files": [{"filename": target.name, "size": target.stat().st_size},
                      {"filename": archive.name, "size": archive.stat().st_size}]}


@app.get("/api/backups")
def list_backups(user=Depends(require("super_admin"))):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    return [{"filename": path.name, "size": path.stat().st_size,
             "kind": _backup_kind(path),
             "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
            for path in sorted([*BACKUPS.glob("negrosky_*.db"), *BACKUPS.glob("negrosky_*.zip")], key=lambda item: item.stat().st_mtime, reverse=True)]


@app.get("/api/backups/{filename}")
def download_backup(filename: str, user=Depends(require("super_admin"))):
    path = (BACKUPS / filename).resolve()
    if path.parent != BACKUPS.resolve() or not path.exists() or path.suffix.lower() not in {".db", ".zip"}:
        raise HTTPException(status_code=404, detail="Respaldo no encontrado")
    media_type = "application/zip" if path.suffix.lower() == ".zip" else "application/octet-stream"
    return FileResponse(path, filename=path.name, media_type=media_type)


@app.post("/api/backup-restore")
def restore_backup(data: RestoreBackupInput, user=Depends(require("super_admin"))):
    source = (BACKUPS / data.filename).resolve()
    if source.parent != BACKUPS.resolve() or not source.exists() or source.suffix.lower() not in {".db", ".zip"}:
        raise HTTPException(status_code=404, detail="Respaldo no encontrado")
    current = create_backup("prerestore")
    restored = _restore_backup_path(source) or {}
    init_db()
    return {"status": "restored", "filename": data.filename, "safety_backup": current.name,
            "restored_files": restored.get("restored_files", 0),
            "message": (
                "Restauración terminada. La base de datos y sus imágenes integradas "
                f"fueron recuperadas; archivos externos recuperados: "
                f"{restored.get('restored_files', 0)}. Inicia sesión nuevamente."
            )}


@app.post("/api/backup-restore-file")
async def restore_backup_file(request: Request, user=Depends(require("super_admin"))):
    """Instala un respaldo .db seleccionado desde el computador."""
    data = await request.json()
    filename = Path(str(data.get("filename") or "respaldo.db")).name
    encoded = str(data.get("data") or "")
    if not filename.lower().endswith((".db", ".zip")) or not encoded:
        raise HTTPException(status_code=422, detail="Selecciona un archivo .db o .zip válido")
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception:
        raise HTTPException(status_code=422, detail="La copia seleccionada no es válida")
    if len(raw) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="La copia supera el límite de 200 MB")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    uploaded = BACKUPS / ("uploaded_" + filename)
    uploaded.write_bytes(raw)
    current = create_backup("prerestore")
    try:
        restored = _restore_backup_path(uploaded) or {}
    finally:
        uploaded.unlink(missing_ok=True)
    init_db()
    return {"status": "restored", "filename": filename, "safety_backup": current.name,
            "restored_files": restored.get("restored_files", 0),
            "message": (
                "Copia instalada. La base de datos y sus imágenes integradas fueron "
                f"recuperadas; archivos externos recuperados: "
                f"{restored.get('restored_files', 0)}. Inicia sesión nuevamente."
            )}


@app.get("/api/export/{kind}")
def export_data(kind: str, tenant_id: int | None = None,
                user=Depends(require("super_admin", "business_admin"))):
    scope = tenant_scope(user, tenant_id)
    queries = {
        "customers": ("""SELECT c.name,c.phone,b.name AS origin_branch,c.status,c.tags,c.notes,c.created_at
            FROM customers c LEFT JOIN branches b ON b.id=c.origin_branch_id
            WHERE c.tenant_id=? ORDER BY c.id""", (scope,)),
        "purchases": ("""SELECT p.created_at,c.name AS customer,c.phone,lp.name AS campaign,
            b.name AS branch,u.name AS worker FROM purchases p JOIN customers c ON c.id=p.customer_id
            JOIN loyalty_programs lp ON lp.id=p.program_id JOIN branches b ON b.id=p.branch_id
            JOIN users u ON u.id=p.worker_id WHERE p.tenant_id=? ORDER BY p.id""", (scope,)),
        "rewards": ("""SELECT r.unlocked_at,r.claimed_at,c.name AS customer,c.phone,
            lp.name AS campaign,r.name AS reward,r.status,b.name AS branch
            FROM rewards r JOIN customers c ON c.id=r.customer_id JOIN loyalty_programs lp ON lp.id=r.program_id
            LEFT JOIN branches b ON b.id=r.branch_id WHERE r.tenant_id=? ORDER BY r.id""", (scope,)),
    }
    if kind not in queries:
        raise HTTPException(status_code=404, detail="Exportación no disponible")
    with connection() as con:
        rows = con.execute(*queries[kind]).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys())
        writer.writerows([tuple(row) for row in rows])
    else:
        writer.writerow(["Sin datos"])
    content = "\ufeff" + output.getvalue()
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="negrosky_{kind}.csv"'})


@app.get("/api/search")
def global_search(q: str, tenant_id: int | None = None,
                  user=Depends(require("super_admin", "business_admin"))):
    if len(q.strip()) < 2:
        return {"businesses": [], "branches": [], "users": [], "customers": []}
    like = f"%{q.strip()}%"
    scope = None if user["role"] == "super_admin" and tenant_id is None else tenant_scope(user, tenant_id)
    with connection() as con:
        businesses = con.execute("SELECT id,name,slug,status FROM tenants WHERE (? IS NULL OR id=?) AND (name LIKE ? OR slug LIKE ?) LIMIT 20", (scope, scope, like, like)).fetchall()
        branches = con.execute("SELECT id,tenant_id,name,city,status FROM branches WHERE (? IS NULL OR tenant_id=?) AND (name LIKE ? OR city LIKE ?) LIMIT 20", (scope, scope, like, like)).fetchall()
        users = con.execute("SELECT id,tenant_id,name,username,role,status FROM users WHERE (? IS NULL OR tenant_id=?) AND (name LIKE ? OR username LIKE ? OR email LIKE ?) LIMIT 20", (scope, scope, like, like, like)).fetchall()
        customers = con.execute("SELECT id,tenant_id,name,phone,status FROM customers WHERE (? IS NULL OR tenant_id=?) AND (name LIKE ? OR phone LIKE ?) LIMIT 20", (scope, scope, like, like)).fetchall()
    return {"businesses":[row_dict(x) for x in businesses],"branches":[row_dict(x) for x in branches],
            "users":[row_dict(x) for x in users],"customers":[row_dict(x) for x in customers]}


@app.get("/api/system/diagnostics")
def diagnostics(user=Depends(require("super_admin"))):
    db_path = database_path()
    BACKUPS.mkdir(parents=True, exist_ok=True)
    with connection() as con:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        stats = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                 for table in ("tenants", "branches", "users", "customers", "purchases", "rewards", "appointments", "notifications")}
    usage = shutil.disk_usage(ROOT)
    return {"status": "ok" if integrity == "ok" else "error", "version": "3.0.50",
            "database_integrity": integrity, "database_size": db_path.stat().st_size if db_path.exists() else 0,
            "free_disk_bytes": usage.free, "backups": len(list(BACKUPS.glob("negrosky_*.db"))), "records": stats,
            "error_log_exists": (ROOT / "servidor_error.log").exists()}


@app.post("/api/system/reset")
def reset_platform(data: ResetPlatformInput, user=Depends(require("super_admin"))):
    if data.confirmation != "BORRAR TODO":
        raise HTTPException(status_code=422, detail="Escribe exactamente BORRAR TODO")
    backup = create_backup("reset")
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        for table in ("operation_token_rewards", "notifications", "appointments", "appointment_services",
                      "purchases", "rewards", "operation_tokens", "loyalty_cards", "loyalty_programs",
                      "customers", "feature_modules", "business_hours", "program_icons", "business_branding", "support_codes"):
            con.execute(f"DELETE FROM {table}")
        con.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE role!='super_admin')")
        con.execute("DELETE FROM audit_logs")
        con.execute("DELETE FROM users WHERE role!='super_admin'")
        con.execute("DELETE FROM branches")
        con.execute("DELETE FROM tenants")
        audit(con, user, "reset", "platform", None, {"backup": backup.name})
    return {"status": "reset", "backup": backup.name, "super_admins_preserved": True}


@app.get("/api/raffles")
def list_raffles(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin", "branch_admin"))):
    with connection() as con:
        if user["role"] == "super_admin" and tenant_id is None: rows=con.execute("SELECT * FROM raffles ORDER BY id DESC").fetchall()
        else:
            scope=tenant_scope(user, tenant_id); rows=con.execute("SELECT * FROM raffles WHERE tenant_id=? ORDER BY id DESC",(scope,)).fetchall()
            if not module_enabled(con, scope, "raffles", user.get("branch_id")):
                return []
        return [row_dict(r) for r in rows]

@app.post("/api/raffles", status_code=201)
def create_raffle(data: RaffleInput, user=Depends(require("super_admin", "business_admin"))):
    scope=tenant_scope(user,data.tenant_id)
    with connection() as con:
        require_user_module(con, user, "raffles")
        cur=con.execute("INSERT INTO raffles(tenant_id,name,description,image_url,ticket_price,ticket_count,draw_at,status,tickets_per_purchase,customer_ticket_limit) VALUES(?,?,?,?,?,?,?, 'active',?,?)",(scope,data.name,data.description,data.image_url,data.ticket_price,data.ticket_count,data.draw_at,data.tickets_per_purchase,data.customer_ticket_limit)); return row_dict(con.execute("SELECT * FROM raffles WHERE id=?",(cur.lastrowid,)).fetchone())

@app.put("/api/raffles/{raffle_id}/status")
def raffle_status(raffle_id:int,data:RaffleStatusInput,user=Depends(require("super_admin","business_admin"))):
    with connection() as con:
        r=con.execute("SELECT * FROM raffles WHERE id=?",(raffle_id,)).fetchone()
        if not r: raise HTTPException(404,"Rifa no encontrada")
        tenant_scope(user,r["tenant_id"]);require_user_module(con,user,"raffles");con.execute("UPDATE raffles SET status=? WHERE id=?",("active" if data.enabled else "paused",raffle_id));return row_dict(con.execute("SELECT * FROM raffles WHERE id=?",(raffle_id,)).fetchone())

@app.put("/api/raffles/{raffle_id}")
def update_raffle(raffle_id:int,data:RaffleInput,user=Depends(require("super_admin","business_admin"))):
    with connection() as con:
        r=con.execute("SELECT * FROM raffles WHERE id=?",(raffle_id,)).fetchone()
        if not r: raise HTTPException(404,"Rifa no encontrada")
        scope=tenant_scope(user,r["tenant_id"])
        if data.tenant_id != scope: raise HTTPException(403,"La rifa pertenece a otro negocio")
        require_user_module(con,user,"raffles")
        con.execute("UPDATE raffles SET name=?,description=?,image_url=?,ticket_price=?,ticket_count=?,draw_at=?,tickets_per_purchase=?,customer_ticket_limit=? WHERE id=?",(data.name,data.description,data.image_url,data.ticket_price,data.ticket_count,data.draw_at,data.tickets_per_purchase,data.customer_ticket_limit,raffle_id))
        return row_dict(con.execute("SELECT * FROM raffles WHERE id=?",(raffle_id,)).fetchone())

@app.delete("/api/raffles/{raffle_id}")
def delete_raffle(raffle_id:int,user=Depends(require("super_admin","business_admin"))):
    with connection() as con:
        r=con.execute("SELECT * FROM raffles WHERE id=?",(raffle_id,)).fetchone()
        if not r: raise HTTPException(404,"Rifa no encontrada")
        tenant_scope(user,r["tenant_id"]);require_user_module(con,user,"raffles");con.execute("DELETE FROM raffle_tickets WHERE raffle_id=?",(raffle_id,));con.execute("DELETE FROM raffles WHERE id=?",(raffle_id,));return {"status":"deleted","raffle_id":raffle_id}

@app.post("/api/raffles/{raffle_id}/tickets", status_code=201)
def reserve_raffle_ticket(raffle_id:int,data:RaffleTicketInput,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        r=con.execute("SELECT * FROM raffles WHERE id=?",(raffle_id,)).fetchone()
        if not r or not (user["role"]=="super_admin" or r["tenant_id"]==user.get("tenant_id")): raise HTTPException(404,"Rifa no encontrada")
        require_user_module(con, user, "raffles")
        try: cur=con.execute("INSERT INTO raffle_tickets(raffle_id,ticket_number,customer_name,customer_phone) VALUES(?,?,?,?)",(raffle_id,data.ticket_number,data.customer_name,data.customer_phone))
        except sqlite3.IntegrityError: raise HTTPException(409,"La boleta ya está reservada")
        return row_dict(con.execute("SELECT * FROM raffle_tickets WHERE id=?",(cur.lastrowid,)).fetchone())

@app.post("/api/raffles/tickets/{ticket_id}/validate")
def validate_raffle_ticket(ticket_id:int,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        row=con.execute("SELECT t.*,r.tenant_id FROM raffle_tickets t JOIN raffles r ON r.id=t.raffle_id WHERE t.id=?",(ticket_id,)).fetchone()
        if not row or (user["role"]!="super_admin" and row["tenant_id"]!=user.get("tenant_id")): raise HTTPException(404,"Participación no encontrada")
        require_user_module(con,user,"raffles");con.execute("UPDATE raffle_tickets SET status='reserved' WHERE id=? AND status='pending'",(ticket_id,));return row_dict(con.execute("SELECT * FROM raffle_tickets WHERE id=?",(ticket_id,)).fetchone())

@app.post("/api/raffles/tickets/validate-code")
def validate_raffle_ticket_code(data: dict,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    code=str(data.get("code") or "").strip().upper()
    if not code: raise HTTPException(422,"Escribe un código de boleta")
    with connection() as con:
        row=con.execute("SELECT t.*,r.name raffle_name,r.tenant_id FROM raffle_tickets t JOIN raffles r ON r.id=t.raffle_id WHERE upper(t.ticket_number)=?",(code,)).fetchone()
        if not row: raise HTTPException(404,"Código de boleta no encontrado")
        tenant_scope(user,row["tenant_id"]);require_user_module(con,user,"raffles")
        if row["status"]!='pending': raise HTTPException(409,"Esta boleta ya fue validada")
        con.execute("UPDATE raffle_tickets SET status='reserved' WHERE id=?",(row["id"],))
        return row_dict(con.execute("SELECT t.*,r.name raffle_name FROM raffle_tickets t JOIN raffles r ON r.id=t.raffle_id WHERE t.id=?",(row["id"],)).fetchone())

@app.get("/api/raffles/tickets/{ticket_id}/qr.png")
def raffle_ticket_qr(ticket_id:int,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        row=con.execute("SELECT t.ticket_number,r.tenant_id FROM raffle_tickets t JOIN raffles r ON r.id=t.raffle_id WHERE t.id=?",(ticket_id,)).fetchone()
        if not row: raise HTTPException(404,"Boleta no encontrada")
        tenant_scope(user,row["tenant_id"])
    import qrcode
    image=qrcode.make(row["ticket_number"]);buf=io.BytesIO();image.save(buf,format="PNG");buf.seek(0)
    return StreamingResponse(buf,media_type="image/png",headers={"Cache-Control":"no-store"})

def raffle_operation_row(con, code, user):
    scope=None if user.get("role")=="super_admin" else user.get("tenant_id")
    sql="""SELECT x.*,r.name raffle_name,c.name customer_name,c.phone customer_phone,r.tenant_id
        FROM raffle_operation_tokens x JOIN raffles r ON r.id=x.raffle_id JOIN customers c ON c.id=x.customer_id
        WHERE x.code=?"""
    args=[str(code).strip()]
    if scope is not None: sql += " AND x.tenant_id=?"; args.append(scope)
    token=con.execute(sql,args).fetchone()
    if not token: raise HTTPException(404,"Código de rifa no válido para este negocio")
    if token["branch_id"] is not None and user.get("branch_id") and token["branch_id"]!=user["branch_id"]:
        raise HTTPException(403,"Este QR pertenece a otra sucursal")
    if token["used_at"]: raise HTTPException(409,"Esta participación ya fue permitida")
    if token["rejected_at"]: raise HTTPException(409,"Esta participación ya fue rechazada")
    if datetime.fromisoformat(token["expires_at"]) < datetime.now(timezone.utc): raise HTTPException(409,"El código de la rifa venció")
    if user.get("role")!="super_admin":
        require_user_module(con,user,"raffles",user.get("branch_id"))
        require_worker_access(con, user, "validate_raffle")
    return token

@app.get("/api/raffle-operations/preview/{code}")
def preview_raffle_operation(code:str,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        token=raffle_operation_row(con,code,user)
        ids=json.loads(token["ticket_ids_json"] or "[]")
        marks=','.join('?'*len(ids)) or 'NULL'
        tickets=con.execute(f"SELECT id,ticket_number,status FROM raffle_tickets WHERE id IN ({marks}) ORDER BY CAST(ticket_number AS INTEGER),id",ids).fetchall() if ids else []
        return {"code":token["code"],"operation":"raffle","customer_name":token["customer_name"],"customer_phone":token["customer_phone"],"raffle_name":token["raffle_name"],"ticket_numbers":[x["ticket_number"] for x in tickets],"ticket_ids":[x["id"] for x in tickets],"expires_at":token["expires_at"]}

@app.post("/api/raffle-operations/validate")
def validate_raffle_operation(data:dict,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        token=raffle_operation_row(con,data.get("code"),user)
        ids=json.loads(token["ticket_ids_json"] or "[]")
        for ticket_id in ids:
            row=con.execute("SELECT status FROM raffle_tickets WHERE id=? AND raffle_id=?",(ticket_id,token["raffle_id"])).fetchone()
            if not row or row["status"]!='pending': raise HTTPException(409,"Una de las boletas ya no está pendiente")
        if ids:
            con.execute(f"UPDATE raffle_tickets SET status='reserved' WHERE id IN ({','.join('?'*len(ids))})",ids)
        validated_at=datetime.now(timezone.utc).isoformat()
        seller_name=user.get("name") or user.get("username") or "Trabajador"
        con.execute("UPDATE raffle_operation_tokens SET used_at=?,validated_by_name=?,validated_at=? WHERE id=?",(validated_at,seller_name,validated_at,token["id"]))
        numbers=[x["ticket_number"] for x in con.execute(f"SELECT ticket_number FROM raffle_tickets WHERE id IN ({','.join('?'*len(ids))})",ids).fetchall()] if ids else []
        return {"status":"validated","customer_name":token["customer_name"],"raffle_name":token["raffle_name"],"ticket_numbers":numbers,"seller_name":seller_name,"validated_at":validated_at}

@app.post("/api/raffle-operations/reject")
def reject_raffle_operation(data:dict,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        con.execute("BEGIN IMMEDIATE")
        token=raffle_operation_row(con,data.get("code"),user)
        ids=json.loads(token["ticket_ids_json"] or "[]")
        if ids: con.execute(f"DELETE FROM raffle_tickets WHERE id IN ({','.join('?'*len(ids))}) AND status='pending'",ids)
        con.execute("UPDATE raffle_operation_tokens SET rejected_at=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),token["id"]))
        return {"status":"rejected","customer_name":token["customer_name"],"raffle_name":token["raffle_name"],"ticket_numbers":[],"rejected_at":datetime.now(timezone.utc).isoformat()}

@app.get("/api/public/{slug}/raffles/{raffle_id}/tickets")
def public_raffle_numbers(slug:str,raffle_id:int):
    with connection() as con:
        tenant=con.execute("SELECT id FROM tenants WHERE slug=? AND status='active'",(slug,)).fetchone()
        if not tenant: raise HTTPException(404,"Negocio no encontrado")
        r=con.execute("SELECT * FROM raffles WHERE id=? AND tenant_id=? AND status='active'",(raffle_id,tenant["id"])).fetchone()
        if not r: raise HTTPException(404,"Rifa no disponible")
        used={int(x["ticket_number"]) for x in con.execute("SELECT ticket_number FROM raffle_tickets WHERE raffle_id=? AND status IN ('reserved','winner')",(raffle_id,)).fetchall() if str(x["ticket_number"]).isdigit()}
        pending={int(x["ticket_number"]) for x in con.execute("SELECT ticket_number FROM raffle_tickets WHERE raffle_id=? AND status='pending'",(raffle_id,)).fetchall() if str(x["ticket_number"]).isdigit()}
        total=r["ticket_count"] or 0
        return {"total":total,"max_per_purchase":r["tickets_per_purchase"] or 1,"used":sorted(used),"pending":sorted(pending),"available":[] if not total else [n for n in range(1,total+1) if n not in used and n not in pending]}

@app.get("/api/raffles/tickets/pending")
def pending_raffle_tickets(tenant_id:int|None=None,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        scope=None if user["role"]=="super_admin" and tenant_id is None else tenant_scope(user,tenant_id)
        sql="""SELECT t.*,r.name raffle_name,r.tenant_id,
            (SELECT x.code FROM raffle_operation_tokens x
             WHERE x.raffle_id=t.raffle_id AND EXISTS (SELECT 1 FROM json_each(x.ticket_ids_json) j WHERE CAST(j.value AS INTEGER)=t.id)
             AND x.used_at IS NULL AND x.rejected_at IS NULL LIMIT 1) AS operation_code
            FROM raffle_tickets t JOIN raffles r ON r.id=t.raffle_id WHERE t.status='pending'"""
        args=[]
        if scope is not None: sql += " AND r.tenant_id=?"; args.append(scope)
        return [row_dict(x) for x in con.execute(sql+" ORDER BY t.id DESC",args).fetchall()]

@app.delete("/api/raffles/tickets/{ticket_id}")
def reject_raffle_ticket(ticket_id:int,user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        row=con.execute("SELECT t.*,r.tenant_id FROM raffle_tickets t JOIN raffles r ON r.id=t.raffle_id WHERE t.id=?",(ticket_id,)).fetchone()
        if not row: raise HTTPException(404,"Participación no encontrada")
        tenant_scope(user,row["tenant_id"]);require_user_module(con,user,"raffles");con.execute("DELETE FROM raffle_tickets WHERE id=? AND status='pending'",(ticket_id,));return {"status":"rejected","ticket_id":ticket_id}

@app.post("/api/raffles/{raffle_id}/draw")
def draw_raffle(raffle_id:int,user=Depends(require("super_admin","business_admin"))):
    with connection() as con:
        r=con.execute("SELECT * FROM raffles WHERE id=?",(raffle_id,)).fetchone()
        if not r: raise HTTPException(404,"Rifa no encontrada")
        require_user_module(con, user, "raffles")
        tickets=con.execute("SELECT * FROM raffle_tickets WHERE raffle_id=? AND status='reserved'",(raffle_id,)).fetchall()
        if not tickets: raise HTTPException(422,"No hay boletas reservadas")
        winner=tickets[secrets.randbelow(len(tickets))]; con.execute("UPDATE raffle_tickets SET status='winner' WHERE id=?",(winner['id'],)); con.execute("UPDATE raffles SET status='drawn',winner_ticket=?,winner_name=? WHERE id=?",(winner['ticket_number'],winner['customer_name'],raffle_id)); return {"raffle_id":raffle_id,"winner":row_dict(winner)}

@app.get("/api/roulette")
def list_roulette(tenant_id:int|None=None,user=Depends(require("super_admin","business_admin","branch_admin"))):
    with connection() as con:
        scope=None if user["role"]=="super_admin" and tenant_id is None else tenant_scope(user,tenant_id); rows=con.execute("SELECT * FROM roulette_configs"+("" if scope is None else " WHERE tenant_id=?"),( ) if scope is None else (scope,)).fetchall(); out=[]
        if scope is not None and not module_enabled(con, scope, "roulette", user.get("branch_id")):
            return []
        for r in rows: d=row_dict(r); d["prizes"]=json.loads(d.pop("prizes_json")); out.append(d)
        return out

@app.post("/api/roulette", status_code=201)
def create_roulette(data:RouletteInput,user=Depends(require("super_admin","business_admin"))):
    scope=tenant_scope(user,data.tenant_id)
    with connection() as con:
        require_user_module(con, user, "roulette")
        cur=con.execute("INSERT INTO roulette_configs(tenant_id,name,prizes_json,difficulty,schedule_json,enabled) VALUES(?,?,?,?,?,?)",(scope,data.name,json.dumps(data.prizes,ensure_ascii=False),data.difficulty,data.schedule,int(data.enabled))); d=row_dict(con.execute("SELECT * FROM roulette_configs WHERE id=?",(cur.lastrowid,)).fetchone()); d["prizes"]=data.prizes; d.pop("prizes_json"); return d

@app.put("/api/roulette/{config_id}/status")
def roulette_status(config_id: int, data: RouletteStatusInput,
                    user=Depends(require("super_admin", "business_admin"))):
    with connection() as con:
        roulette = con.execute("SELECT * FROM roulette_configs WHERE id=?", (config_id,)).fetchone()
        if not roulette:
            raise HTTPException(status_code=404, detail="Ruleta no encontrada")
        scope = tenant_scope(user, roulette["tenant_id"])
        require_user_module(con, user, "roulette")
        con.execute("UPDATE roulette_configs SET enabled=? WHERE id=?", (int(data.enabled), config_id))
        audit(con, user, "activate" if data.enabled else "pause", "roulette", config_id,
              {"enabled": data.enabled, "tenant_id": scope})
        updated = row_dict(con.execute("SELECT * FROM roulette_configs WHERE id=?", (config_id,)).fetchone())
        updated["prizes"] = json.loads(updated.pop("prizes_json"))
        return updated

@app.put("/api/roulette/{config_id}")
def update_roulette(config_id:int,data:RouletteInput,user=Depends(require("super_admin","business_admin"))):
    with connection() as con:
        r=con.execute("SELECT * FROM roulette_configs WHERE id=?",(config_id,)).fetchone()
        if not r: raise HTTPException(404,"Ruleta no encontrada")
        scope=tenant_scope(user,r["tenant_id"])
        if data.tenant_id != scope: raise HTTPException(403,"La ruleta pertenece a otro negocio")
        require_user_module(con,user,"roulette")
        con.execute("UPDATE roulette_configs SET name=?,prizes_json=?,difficulty=?,schedule_json=?,enabled=? WHERE id=?",(data.name,json.dumps(data.prizes,ensure_ascii=False),data.difficulty,data.schedule,int(data.enabled),config_id))
        d=row_dict(con.execute("SELECT * FROM roulette_configs WHERE id=?",(config_id,)).fetchone());d["prizes"]=json.loads(d.pop("prizes_json"));return d

@app.delete("/api/roulette/{config_id}")
def delete_roulette(config_id:int,user=Depends(require("super_admin","business_admin"))):
    with connection() as con:
        r=con.execute("SELECT * FROM roulette_configs WHERE id=?",(config_id,)).fetchone()
        if not r: raise HTTPException(404,"Ruleta no encontrada")
        tenant_scope(user,r["tenant_id"]);require_user_module(con,user,"roulette")
        con.execute("DELETE FROM roulette_spins WHERE config_id=?",(config_id,));con.execute("DELETE FROM roulette_configs WHERE id=?",(config_id,));return {"status":"deleted","config_id":config_id}

@app.post("/api/roulette/{config_id}/spin")
def spin_roulette(config_id:int, customer_name:str="", customer_phone:str="", user=Depends(require("super_admin","business_admin","branch_admin","worker"))):
    with connection() as con:
        r=con.execute("SELECT * FROM roulette_configs WHERE id=? AND enabled=1",(config_id,)).fetchone()
        if not r: raise HTTPException(404,"Ruleta no disponible")
        require_user_module(con, user, "roulette")
        prizes=json.loads(r["prizes_json"]); prize=prizes[secrets.randbelow(len(prizes))]; con.execute("INSERT INTO roulette_spins(config_id,customer_name,customer_phone,prize) VALUES(?,?,?,?)",(config_id,customer_name,customer_phone,prize)); return {"prize":prize,"config_id":config_id}

@app.post("/api/public/me/roulette/{config_id}/spin")
def public_spin_roulette(config_id:int, customer=Depends(current_customer)):
    with connection() as con:
        if not module_enabled(con, customer["tenant_id"], "public_page", customer.get("origin_branch_id")):
            raise HTTPException(status_code=404, detail="Ruleta no disponible")
        if not module_enabled(con, customer["tenant_id"], "roulette", customer.get("origin_branch_id")):
            raise HTTPException(status_code=404, detail="Ruleta no disponible")
        r=con.execute("SELECT * FROM roulette_configs WHERE id=? AND tenant_id=? AND enabled=1",(config_id,customer["tenant_id"])).fetchone()
        if not r: raise HTTPException(404,"Ruleta no disponible")
        prizes=json.loads(r["prizes_json"]); prize=prizes[secrets.randbelow(len(prizes))]
        con.execute("INSERT INTO roulette_spins(config_id,customer_name,customer_phone,prize) VALUES(?,?,?,?)",(config_id,customer["name"],customer.get("phone"),prize))
        return {"prize":prize,"config_id":config_id}

@app.get("/api/audit")
def list_audit(tenant_id: int | None = None, user=Depends(require("super_admin", "business_admin"))):
    if user["role"] == "super_admin" and tenant_id is None:
        query, params = "SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100", ()
    else:
        scope = tenant_scope(user, tenant_id)
        query, params = "SELECT * FROM audit_logs WHERE tenant_id=? ORDER BY id DESC LIMIT 100", (scope,)
    with connection() as con:
        rows = con.execute(query, params).fetchall()
    return [row_dict(r) for r in rows]
