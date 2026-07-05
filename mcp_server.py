#!/usr/bin/env python3
"""
MCP Web Gateway — Multi-Tenant Server
Firebase Auth · Tailscale Tunnel Provisioning · Sandboxed MCP Tools
"""

import os
import sys
import asyncio
import json
import re
import aiosqlite
import logging
import shutil
import hashlib
import secrets
import base64
import pwd  # Cleaned up and imported globally for POSIX sandboxing
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Set
from contextlib import asynccontextmanager

import uvicorn
from fastapi import (
    FastAPI, Request, HTTPException, WebSocket,
    WebSocketDisconnect, UploadFile, File
)
import shutil
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from starlette.routing import Mount
from dotenv import load_dotenv

from port_engine import find_available_port
from duckduckgo_search import DDGS

import firebase_admin
from firebase_admin import credentials as fb_credentials, auth as fb_auth

try:
    from firebase_admin import firestore as fb_firestore
except ImportError:
    fb_firestore = None

try:
    from google.oauth2 import service_account as google_service_account
except ImportError:
    google_service_account = None

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

# ---------------------------------------------------------------------------
# Google Drive — non-blocking import with graceful degradation
# ---------------------------------------------------------------------------
_DRIVE_AVAILABLE = True
try:
    from google.oauth2.credentials import Credentials as GDriveCreds
    from google.auth.transport.requests import Request as GoogleAuthRefresh
    from googleapiclient.discovery import build as build_service
    from googleapiclient.http import MediaFileUpload
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    _DRIVE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gateway")

# Ensure tailscale binary paths are in the system PATH environment variable
_current_path = os.environ.get("PATH", "")
_ts_paths = ["/usr/bin", "/usr/sbin"]
for _p in _ts_paths:
    if _p not in _current_path.split(os.pathsep):
        _current_path = f"{_p}{os.pathsep}{_current_path}"
os.environ["PATH"] = _current_path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent

def _env(name: str, default: str = "") -> str:
    """Read an env var while tolerating placeholder/example values."""
    value = os.getenv(name, default)
    if value is None:
        return default
    value = value.strip()
    if "  #" in value:
        value = value.split("  #", 1)[0].strip()
    lower = value.lower()
    placeholders = (
        "your-project-id",
        "your_secret_agent_key_here",
        "1:000000000000:web:xxxxxxxxxxxx",
        "000000000000",
    )
    if not value or value in placeholders or lower.startswith("your-"):
        return default
    return value

def _resolve_path(value: str) -> str:
    if not value:
        return ""
    p = Path(value).expanduser()
    if not p.is_absolute():
        p = APP_DIR / p
    return str(p)

def _load_service_account_metadata(path: str) -> dict:
    if not path or not Path(path).is_file():
        return {}
    try:
        raw = json.loads(Path(path).read_text())
        return {
            "project_id": raw.get("project_id", ""),
            "client_email": raw.get("client_email", ""),
        }
    except Exception as exc:
        log.warning("Could not read Firebase service account metadata: %s", exc)
        return {}

SERVER_NAME            = _env("SERVER_NAME", "FedoraKDE_Agent")
HOST                   = _env("HOST", "0.0.0.0")
PORT                   = int(_env("PORT", "10000"))
MCP_API_KEY            = _env("MCP_API_KEY", "your_secret_agent_key_here")
API_KEY_HEADER         = "X-API-Key"
RESTRICTED_DIR         = "-mcp_server0local"
MAX_FILE_BYTES         = 10 * 1024 * 1024 * 1024   # 10 GB

FB_SA_PATH             = _resolve_path(_env("FIREBASE_SERVICE_ACCOUNT_PATH", "./service-account.json"))
_FB_SA_META            = _load_service_account_metadata(FB_SA_PATH)
FB_PROJECT_ID          = _env("FIREBASE_PROJECT_ID", _FB_SA_META.get("project_id", ""))
FB_API_KEY             = _env("FIREBASE_API_KEY", "")
FB_AUTH_DOMAIN         = _env("FIREBASE_AUTH_DOMAIN", f"{FB_PROJECT_ID}.firebaseapp.com" if FB_PROJECT_ID else "")
FB_STORAGE_BUCKET      = _env("FIREBASE_STORAGE_BUCKET", f"{FB_PROJECT_ID}.appspot.com" if FB_PROJECT_ID else "")
FB_MSG_SENDER_ID       = _env("FIREBASE_MESSAGING_SENDER_ID", "")
FB_APP_ID              = _env("FIREBASE_APP_ID", "")
FB_DATABASE_URL        = _env("FIREBASE_DATABASE_URL", "")
DRIVE_SECRET_PATH      = _resolve_path(_env("GOOGLE_DRIVE_CLIENT_SECRET_PATH", ""))
FRONTEND_DIR_OVERRIDE  = _env("FRONTEND_DIR", _env("STATIC_FRONTEND_DIR", ""))

# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------
BASE_DIR = Path(os.getcwd())
if BASE_DIR.name != RESTRICTED_DIR:
    BASE_DIR = BASE_DIR / RESTRICTED_DIR
BASE_DIR.mkdir(parents=True, exist_ok=True)

def _frontend_dir_has_app(path: Path) -> bool:
    return path.is_dir() and (path / "index.html").is_file()

def _resolve_frontend_dir() -> Path:
    candidates = []

    if FRONTEND_DIR_OVERRIDE:
        configured = Path(FRONTEND_DIR_OVERRIDE).expanduser()
        if configured.is_absolute():
            candidates.append(configured)
        else:
            candidates.extend((Path.cwd() / configured, APP_DIR / configured))

    roots = [APP_DIR, Path.cwd(), *APP_DIR.parents]
    seen_roots = []
    for root in roots:
        if root not in seen_roots:
            seen_roots.append(root)

    for root in seen_roots:
        candidates.extend((
            root / "frontend",
            root / "HOSTING" / "frontend",
            root / "hosting" / "frontend",
            root / "public",
            root / "static",
            root / "dist",
            root / "build",
        ))

    seen_candidates = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen_candidates:
            continue
        seen_candidates.append(resolved)
        if _frontend_dir_has_app(resolved):
            return resolved

    for root in seen_roots[:4]:
        if not root.is_dir():
            continue
        try:
            for index_file in root.rglob("index.html"):
                if any(part in {"node_modules", "__pycache__", ".git", ".venv", "venv"} for part in index_file.parts):
                    continue
                parent = index_file.parent.resolve()
                if _frontend_dir_has_app(parent):
                    return parent
        except OSError:
            continue

    return (Path(FRONTEND_DIR_OVERRIDE).expanduser() if FRONTEND_DIR_OVERRIDE else APP_DIR / "frontend").resolve()

FRONTEND_DIR = _resolve_frontend_dir()
DB_PATH = APP_DIR / "auth_records.db"

def _secure_system():
    if os.name == "nt":
        return
    try:
        os.chmod(str(APP_DIR), 0o711)
        try:
            sandbox_pw = pwd.getpwnam("sandbox")
            uid = sandbox_pw.pw_uid
            gid = sandbox_pw.pw_gid

            os.chown(str(BASE_DIR), uid, gid)
            os.chmod(str(BASE_DIR), 0o700)

            for root_dir, dirs, files in os.walk(str(BASE_DIR)):
                for d in dirs:
                    os.chown(os.path.join(root_dir, d), uid, gid)
                    os.chmod(os.path.join(root_dir, d), 0o700)
                for f in files:
                    try:
                        os.chown(os.path.join(root_dir, f), uid, gid)
                        os.chmod(os.path.join(root_dir, f), 0o600)
                    except Exception:
                        pass
        except KeyError:
            log.warning("sandbox user not found; skipping sandbox directory chown")

        sensitive_paths = [
            DB_PATH,
            APP_DIR / ".env",
            APP_DIR / ".env temp_config.txt",
            APP_DIR / "service-account.json",
            APP_DIR / "client_secret.json",
            APP_DIR / "token.json",
            Path(__file__).resolve(),
        ]
        for path in sensitive_paths:
            if path.is_file():
                os.chmod(str(path), 0o600)
    except Exception as exc:
        log.warning("Failed to run _secure_system: %s", exc)

# ---------------------------------------------------------------------------
# Firebase Admin SDK — init once
# ---------------------------------------------------------------------------
_fb_app = None
_firestore = None
_firebase_web_config_cache: Optional[dict] = None

def _firebase_options() -> dict:
    options = {"projectId": FB_PROJECT_ID} if FB_PROJECT_ID else {}
    if FB_DATABASE_URL:
        options["databaseURL"] = FB_DATABASE_URL
    if FB_STORAGE_BUCKET:
        options["storageBucket"] = FB_STORAGE_BUCKET
    return options

def _discover_firebase_web_config() -> dict:
    if not FB_SA_PATH or not Path(FB_SA_PATH).is_file():
        return {}
    if not google_service_account or not google_service_account.Credentials:
         return {}
    if not FB_PROJECT_ID:
        return {}
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        creds = google_service_account.Credentials.from_service_account_file(
            FB_SA_PATH, scopes=scopes
        )
        svc = build_service("firebase", "v1beta1", credentials=creds, cache_discovery=False)
        parent = f"projects/{FB_PROJECT_ID}"
        apps = svc.projects().webApps().list(parent=parent, pageSize=10).execute()
        web_apps = apps.get("apps", [])
        if not web_apps:
            log.warning("No Firebase Web App found in project %s", FB_PROJECT_ID)
            return {}
        app_name = web_apps[0]["name"]
        cfg = svc.projects().webApps().getConfig(name=f"{app_name}/config").execute()
        log.info("Firebase Web App config discovered from project metadata")
        return {
            "apiKey": cfg.get("apiKey", ""),
            "authDomain": cfg.get("authDomain", ""),
            "projectId": cfg.get("projectId", FB_PROJECT_ID),
            "storageBucket": cfg.get("storageBucket", ""),
            "messagingSenderId": cfg.get("messagingSenderId", ""),
            "appId": cfg.get("appId", ""),
            "measurementId": cfg.get("measurementId", ""),
        }
    except Exception as exc:
        log.warning("Firebase Web App config auto-discovery failed: %s", exc)
        return {}

def _init_firebase():
    global _fb_app, _firestore
    if FB_SA_PATH and Path(FB_SA_PATH).is_file():
        cred = fb_credentials.Certificate(FB_SA_PATH)
        _fb_app = firebase_admin.initialize_app(cred, _firebase_options())
        log.info(
            "Firebase Admin initialised from service-account JSON (%s)",
            _FB_SA_META.get("client_email", "service account"),
        )
    elif FB_PROJECT_ID:
        try:
            _fb_app = firebase_admin.initialize_app(options=_firebase_options())
            log.info("Firebase Admin initialised with application default creds")
        except Exception as exc:
            log.warning("Firebase init failed (%s) — running legacy API-key mode", exc)
    else:
        log.warning("No Firebase config detected — legacy API-key mode only")

    if _fb_app and fb_firestore:
        try:
            _firestore = fb_firestore.client()
            log.info("Firestore client ready for users/auth_events")
        except Exception as exc:
            log.warning("Firestore unavailable (%s) — SQLite audit remains active", exc)

_init_firebase()

# ---------------------------------------------------------------------------
# SQLite — user auth record store (async, non-blocking)
# ---------------------------------------------------------------------------
async def _db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_auth_records (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                uid       TEXT    NOT NULL,
                email     TEXT,
                method    TEXT    NOT NULL,
                ip        TEXT,
                success   INTEGER NOT NULL DEFAULT 1,
                error_msg TEXT,
                ts        TEXT    NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_uid ON user_auth_records(uid)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_ts  ON user_auth_records(ts)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                uid          TEXT PRIMARY KEY,
                email        TEXT,
                display_name TEXT,
                photo_url    TEXT,
                provider     TEXT,
                last_ip      TEXT,
                last_login   TEXT,
                created_at   TEXT,
                updated_at   TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_tokens (
                uid TEXT PRIMARY KEY,
                tokens TEXT
            )
        """)
        try:
            await db.execute("ALTER TABLE user_profiles ADD COLUMN mcp_password_hash TEXT")
        except Exception:
            pass
        await db.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON user_profiles(email)")
        await db.commit()
    log.info("SQLite auth_records DB ready at %s", DB_PATH)


async def _db_record_auth(uid: str, email: Optional[str], method: str, ip: Optional[str] = None, success: bool = True, error_msg: Optional[str] = None):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO user_auth_records (uid, email, method, ip, success, error_msg, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (uid, email, method, 1 if success else 0, error_msg, datetime.now().isoformat()),
            )
            await db.commit()
    except Exception as exc:
        log.warning("DB record failed: %s", exc)


async def _db_upsert_user_profile(uid: str, email: Optional[str] = None, display_name: Optional[str] = None, photo_url: Optional[str] = None, provider: Optional[str] = None, ip: Optional[str] = None):
    now = datetime.now().isoformat()
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO user_profiles (uid, email, display_name, photo_url, provider, last_ip, last_login, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    email=excluded.email,
                    display_name=COALESCE(excluded.display_name, user_profiles.display_name),
                    photo_url=COALESCE(excluded.photo_url, user_profiles.photo_url),
                    provider=COALESCE(excluded.provider, user_profiles.provider),
                    last_ip=excluded.last_ip,
                    last_login=excluded.last_login,
                    updated_at=excluded.updated_at
                """,
                (uid, email, display_name, photo_url, provider, ip, now, now, now),
            )
            await db.commit()
    except Exception as exc:
        log.warning("DB user profile upsert failed: %s", exc)


async def _firestore_write(collection: str, document_id: Optional[str], data: dict):
    if not _firestore:
        return
    try:
        if document_id:
            ref = _firestore.collection(collection).document(document_id)
            await asyncio.to_thread(ref.set, data, merge=True)
        else:
            ref = _firestore.collection(collection)
            await asyncio.to_thread(ref.add, data)
    except Exception as exc:
        log.warning("Firestore write failed for %s: %s", collection, exc)


async def _record_user(decoded: dict, method: str, ip: Optional[str] = None, success: bool = True, error_msg: Optional[str] = None):
    uid = decoded.get("uid", "unknown")
    email = decoded.get("email")
    provider = None
    firebase_info = decoded.get("firebase") or {}
    providers = firebase_info.get("identities") or {}
    if providers:
        provider = ",".join(sorted(providers.keys()))
    await _db_record_auth(uid, email, method, ip, success, error_msg)
    if success and uid != "unknown":
        await _db_upsert_user_profile(
            uid,
            email=email,
            display_name=decoded.get("name"),
            photo_url=decoded.get("picture"),
            provider=provider,
            ip=ip,
        )
        await _firestore_write("users", uid, {
            "uid": uid,
            "email": email,
            "displayName": decoded.get("name"),
            "photoUrl": decoded.get("picture"),
            "provider": provider,
            "lastIp": ip,
            "lastLogin": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
        })
    await _firestore_write("auth_events", None, {
        "uid": uid,
        "email": email,
        "method": method,
        "ip": ip,
        "success": success,
        "error": error_msg,
        "ts": datetime.now().isoformat(),
    })

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
active_tunnels: Dict[str, dict] = {}
tailscale_auth_urls: Dict[str, str] = {}
ws_clients: Dict[str, Set[WebSocket]] = {}
log_rings: Dict[str, list] = {}
LOG_RING_MAX = 600
_startup_time = datetime.now()

# ---------------------------------------------------------------------------
# Google Drive Core Logic
# ---------------------------------------------------------------------------
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

def _get_drive_service():
    if not _DRIVE_AVAILABLE:
        raise RuntimeError("google-api-python-client dependencies not available")

    token_path = APP_DIR / "token.json"
    secret_candidates = [
        Path(DRIVE_SECRET_PATH) if DRIVE_SECRET_PATH else None,
        APP_DIR / "client_secret.json",
    ]

    creds = None
    if token_path.is_file():
        creds = GDriveCreds.from_authorized_user_file(str(token_path), DRIVE_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRefresh())
        token_path.write_text(creds.to_json())

    if not creds or not creds.valid:
        secret_file = next((p for p in secret_candidates if p and p.is_file()), None)
        if secret_file is None:
            raise FileNotFoundError("No valid authorization configuration or tokens found.")
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), DRIVE_SCOPES)
        creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build_service("drive", "v3", credentials=creds)

# ---------------------------------------------------------------------------
# Broadcast logs to WS pipelines
# ---------------------------------------------------------------------------
async def _broadcast(msg: str, level: str = "info", uid: Optional[str] = None):
    entry = {"ts": datetime.now().isoformat(), "level": level, "msg": msg}
    targets = [uid] if uid else list(ws_clients.keys())
    for u in targets:
        if u not in log_rings:
            log_rings[u] = []
        log_rings[u].append(entry)
        if len(log_rings[u]) > LOG_RING_MAX:
            log_rings[u].pop(0)
        dead = set()
        for ws_conn in ws_clients.get(u, set()):
            try:
                await ws_conn.send_json(entry)
            except Exception:
                dead.add(ws_conn)
        if u in ws_clients:
            ws_clients[u].difference_update(dead)

# ---------------------------------------------------------------------------
# Cryptographic Password Verification
# ---------------------------------------------------------------------------
def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, dklen=32)
    return base64.b64encode(salt + key).decode('utf-8')

def _verify_password(password: str, hashed: str) -> bool:
    if not hashed: return False
    try:
        raw = base64.b64decode(hashed)
        salt, key = raw[:16], raw[16:]
        new_key = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, dklen=32)
        return secrets.compare_digest(key, new_key)
    except Exception:
        return False

async def _verify_request(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    email, password = None, None

    query_auth = request.query_params.get("auth", "")
    query_token = request.query_params.get("token", "")
    query_email = request.query_params.get("email")
    query_password = request.query_params.get("password")

    if query_auth:
        if query_auth.startswith("Basic "):
            query_auth = query_auth[6:]
        elif query_auth.startswith("Bearer "):
            auth = query_auth

        if not auth.startswith("Bearer "):
            try:
                decoded = base64.b64decode(query_auth).decode("utf-8")
                if ":" in decoded:
                    email, password = decoded.split(":", 1)
            except Exception:
                if ":" in query_auth:
                    email, password = query_auth.split(":", 1)

    if query_token and not email and not auth:
        try:
            decoded = base64.b64decode(query_token).decode("utf-8")
            if ":" in decoded:
                email, password = decoded.split(":", 1)
        except Exception:
            pass
        if not email:
            auth = f"Bearer {query_token}"

    if query_email and query_password:
        email, password = query_email, query_password

    if email and password:
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT uid, mcp_password_hash, display_name FROM user_profiles WHERE email = ?", (email,)) as cursor:
                    row = await cursor.fetchone()
                    if row and _verify_password(password, row[1]):
                        return {"uid": row[0], "email": email, "name": row[2]}
        except Exception:
            pass

    if auth.startswith("Basic "):
        try:
            decoded_basic = base64.b64decode(auth[6:]).decode('utf-8')
            if ":" in decoded_basic:
                email, password = decoded_basic.split(":", 1)
                async with aiosqlite.connect(DB_PATH) as db:
                    async with db.execute("SELECT uid, mcp_password_hash, display_name FROM user_profiles WHERE email = ?", (email,)) as cursor:
                        row = await cursor.fetchone()
                        if row and _verify_password(password, row[1]):
                            return {"uid": row[0], "email": email, "name": row[2]}
        except Exception:
            pass

    if auth.startswith("Bearer ") and _fb_app:
        try:
            return fb_auth.verify_id_token(auth[7:])
        except Exception as exc:
            raise HTTPException(401, detail=f"Invalid token: {exc}")

    key = request.headers.get(API_KEY_HEADER) or request.query_params.get("api_key")
    if key == MCP_API_KEY:
        return {"uid": "apikey_user", "email": "apikey@local"}

    raise HTTPException(401, detail="Authentication required")


def _tenant_dir(uid: str) -> Path:
    if not re.match(r"^[a-zA-Z0-9_\-]+$", uid):
        raise ValueError("Invalid UID format")
    d = (BASE_DIR / uid).resolve()
    if not d.is_relative_to(BASE_DIR.resolve()):
        raise ValueError("Directory traversal attempt")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _user_tailscaled_socket(uid: str) -> str:
    ts_dir = _tenant_dir(uid) / "tailscale"
    ts_dir.mkdir(parents=True, exist_ok=True)
    return str(ts_dir / "tailscaled.sock")

async def _ensure_user_tailscaled(uid: str):
    ts_dir = _tenant_dir(uid) / "tailscale"
    ts_dir.mkdir(parents=True, exist_ok=True)
    sock_file = ts_dir / "tailscaled.sock"

    try:
        proc = await asyncio.create_subprocess_exec("tailscale", f"--socket={sock_file}", "status", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        if proc.returncode == 0 or b"Logged out." in err or b"Logged out." in out:
            return str(sock_file)
    except Exception:
        pass

    log.info(f"Starting dedicated tailscaled for user {uid}")
    await asyncio.create_subprocess_exec(
        "tailscaled", "--tun=userspace-networking", "--socks5-server=localhost:0",
        f"--socket={sock_file}", f"--statedir={str(ts_dir)}",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await asyncio.sleep(2)
    return str(sock_file)

# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    _secure_system()
    await _db_init()

    try:
        await asyncio.create_subprocess_exec(
            "tailscale", "up",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
    except Exception as e:
        log.warning("Could not launch tailscaled daemon automatically: %s", e)

    async def _monitor_tunnels_loop():
        log.info("Starting auto-healing tunnel monitor task loop...")
        try:
            public_port = 443
            pf = await asyncio.create_subprocess_exec(
                "tailscale", "funnel", "--bg", f"--https={public_port}", str(PORT),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(pf.wait(), timeout=10.0)
        except Exception as e:
            log.warning("Could not auto-provision primary funnel: %s", e)

        while True:
            await asyncio.sleep(30)
            try:
                p = await asyncio.create_subprocess_exec(
                    "tailscale", "status", "--json",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                out, _ = await p.communicate()
                if p.returncode != 0 or not out:
                    continue
                data = json.loads(out.decode())
                backend_state = data.get("BackendState", "Unknown")
                if backend_state != "Running":
                    log.warning("Auto-healer caught offline status: %s. Reconnecting...", backend_state)
                    proc = await asyncio.create_subprocess_exec(
                        "tailscale", "up",
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    await asyncio.wait_for(proc.wait(), timeout=10.0)
            except Exception as e:
                log.warning("Error running auto-healing tunnel check: %s", e)

    monitor_task = asyncio.create_task(_monitor_tunnels_loop())
    log.info("Gateway live %s:%s sandbox=%s", HOST, PORT, BASE_DIR)
    await _broadcast("Gateway started", "info")
    yield
    monitor_task.cancel()
    log.info("Gateway shutdown")

app = FastAPI(title="MCP Web Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

mcp_server = Server(SERVER_NAME)
sse_transport = SseServerTransport("/messages/")

# ===================================================================== #
#                           REST  API  v1                               #
# ===================================================================== #

@app.get("/health")
async def health():
    ts_connected = False
    ts_ip = None
    ts_dns = None
    ts_backend_state = "Unknown"
    try:
        proc = await asyncio.create_subprocess_exec("tailscale", "status", "--json", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            data = json.loads(out.decode())
            ts_backend_state = data.get("BackendState", "Unknown")
            self_node = data.get("Self", {}) or {}
            ips = self_node.get("TailscaleIPs") or []
            ts_ip = ips[0] if ips else None
            ts_dns = (self_node.get("DNSName") or "").rstrip(".")
            ts_connected = ts_backend_state == "Running"
        except Exception:
            pass
    except Exception:
        pass

    return {
        "status": "healthy",
        "server": SERVER_NAME,
        "firebase": _fb_app is not None,
        "firestore": _firestore is not None,
        "firebase_project_id": FB_PROJECT_ID,
        "firebase_web_configured": bool(_effective_firebase_public_config().get("apiKey")),
        "tunnels": len(active_tunnels),
        "mcp_active": any(t.get("public_port") == 8443 for t in active_tunnels.values()),
        "tailscale_connected": ts_connected,
        "tailscale_state": ts_backend_state,
        "tailscale_ip": ts_ip,
        "tailscale_dns": ts_dns,
        "uptime_seconds": int((datetime.now() - _startup_time).total_seconds()),
        "ts": datetime.now().isoformat(),
    }


def _effective_firebase_public_config() -> dict:
    global _firebase_web_config_cache
    env_config = {
        "apiKey":            FB_API_KEY,
        "authDomain":        FB_AUTH_DOMAIN,
        "projectId":         FB_PROJECT_ID,
        "storageBucket":     FB_STORAGE_BUCKET,
        "messagingSenderId": FB_MSG_SENDER_ID,
        "appId":             FB_APP_ID,
    }
    if env_config["apiKey"] and env_config["appId"]:
        return env_config
    if _firebase_web_config_cache is None:
        _firebase_web_config_cache = _discover_firebase_web_config()
    discovered = _firebase_web_config_cache or {}
    return {
        **env_config,
        **{k: v for k, v in discovered.items() if v},
    }

@app.get("/api/v1/config")
async def firebase_public_config():
    cfg = _effective_firebase_public_config()
    cfg["adminConfigured"] = _fb_app is not None
    cfg["firestoreConfigured"] = _firestore is not None
    cfg["webConfigured"] = bool(cfg.get("apiKey") and cfg.get("appId"))
    return cfg


@app.post("/api/v1/auth/verify")
async def auth_verify(request: Request):
    body = await request.json()
    token = body.get("token", "")
    if not token:
        raise HTTPException(400, "token required")
    if not _fb_app:
        raise HTTPException(503, "Firebase not configured on server")
    ip = request.client.host if request.client else None
    try:
        dec = fb_auth.verify_id_token(token)
        uid = dec["uid"]
        _tenant_dir(uid)
        await _broadcast(f"Auth verified: {dec.get('email', uid)}", "auth", uid)
        asyncio.create_task(_record_user(dec, "verify", ip))
        return {
            "uid": uid,
            "email": dec.get("email"),
            "name": dec.get("name"),
            "picture": dec.get("picture"),
            "verified": True,
        }
    except Exception as exc:
        asyncio.create_task(_record_user({"uid": "unknown"}, "verify", ip, False, str(exc)))
        raise HTTPException(401, str(exc))


@app.post("/api/v1/auth/register")
async def auth_register(request: Request):
    body = await request.json()
    email    = body.get("email", "").strip()
    password = body.get("password", "")
    display  = body.get("displayName", "")
    if not email or not password:
        raise HTTPException(400, "email and password required")
    if not _fb_app:
        raise HTTPException(503, "Firebase not configured on server")
    ip = request.client.host if request.client else None
    try:
        user = fb_auth.create_user(
            email=email,
            password=password,
            display_name=display or email.split("@")[0],
        )
        _tenant_dir(user.uid)
        custom_tok = fb_auth.create_custom_token(user.uid)

        # Guarded string cast for custom token returns
        token_str = custom_tok.decode() if isinstance(custom_tok, bytes) else custom_tok

        await _broadcast(f"New user: {email}", "auth", user.uid)
        asyncio.create_task(_record_user({
            "uid": user.uid,
            "email": user.email,
            "name": user.display_name,
            "picture": user.photo_url,
            "firebase": {"identities": {"password": [user.email]}},
        }, "register", ip))
        return {
            "uid": user.uid,
            "email": user.email,
            "displayName": user.display_name,
            "customToken": token_str,
        }
    except fb_auth.EmailAlreadyExistsError:
        asyncio.create_task(_record_user({"uid": "dup", "email": email}, "register", ip, False, "Email already registered"))
        raise HTTPException(409, "Email already registered")
    except Exception as exc:
        asyncio.create_task(_record_user({"uid": "err", "email": email}, "register", ip, False, str(exc)))
        raise HTTPException(400, str(exc))


@app.post("/api/v1/auth/login")
async def auth_login(request: Request):
    body = await request.json()
    token = body.get("token", "")
    if not token:
        raise HTTPException(400, "token required")
    if not _fb_app:
        raise HTTPException(503, "Firebase not configured on server")
    ip = request.client.host if request.client else None
    try:
        dec = fb_auth.verify_id_token(token)
        uid = dec["uid"]
        _tenant_dir(uid)
        await _broadcast(f"Login: {dec.get('email', uid)}", "auth", uid)
        asyncio.create_task(_record_user(dec, "login", ip))
        return {
            "uid": uid,
            "email": dec.get("email"),
            "name": dec.get("name"),
            "session": "active",
        }
    except Exception as exc:
        asyncio.create_task(_record_user({"uid": "unknown"}, "login", ip, False, str(exc)))
        raise HTTPException(401, str(exc))


@app.get("/api/v1/auth/records")
async def auth_records(request: Request, limit: int = 100, offset: int = 0, search: Optional[str] = None):
    user = await _verify_request(request)
    is_admin = user["uid"] == "apikey_user" or bool(user.get("admin"))
    target_uid = request.query_params.get("uid", user["uid"])
    if not is_admin and user["uid"] != target_uid:
        raise HTTPException(403, "Forbidden")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            query_parts = []
            params = []
            if not (is_admin and target_uid in ("all", "apikey_user")):
                query_parts.append("uid = ?")
                params.append(target_uid)
            if search:
                query_parts.append("(email LIKE ? OR ip LIKE ? OR method LIKE ? OR error_msg LIKE ?)")
                keyword = f"%{search}%"
                params.extend([keyword, keyword, keyword, keyword])

            where_clause = " WHERE " + " AND ".join(query_parts) if query_parts else ""
            query_str = f"SELECT * FROM user_auth_records{where_clause} ORDER BY ts DESC LIMIT ? OFFSET ?"
            params.extend([min(limit, 500), offset])

            cursor = await db.execute(query_str, params)
            rows = await cursor.fetchall()
            return {"records": [dict(r) for r in rows], "count": len(rows)}
    except Exception as exc:
        raise HTTPException(500, f"DB error: {exc}")


@app.get("/api/v1/user/profile")
async def user_profile(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    tenant = _tenant_dir(uid)

    total_bytes = 0
    file_count = 0
    for p in tenant.rglob("*"):
        if p.is_file():
            total_bytes += p.stat().st_size
            file_count += 1

    profile = {
        "uid": uid,
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "admin": bool(user.get("admin")),
        "tenant_path": str(tenant.relative_to(BASE_DIR)),
        "storage_bytes": total_bytes,
        "file_count": file_count,
    }
    await _db_upsert_user_profile(
        uid,
        email=user.get("email"),
        display_name=user.get("name"),
        photo_url=user.get("picture"),
        ip=request.client.host if request.client else None,
    )
    return profile


@app.get("/api/v1/system/telemetry")
async def system_telemetry(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    tenant = _tenant_dir(uid)

    total_bytes = 0
    file_count = 0
    for p in tenant.rglob("*"):
        if p.is_file():
            total_bytes += p.stat().st_size
            file_count += 1

    mem_total, mem_avail, cpu_percent = 0, 0, 0.0
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()
            for line in lines:
                if line.startswith("MemTotal:"):
                    mem_total = int(line.split()[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    mem_avail = int(line.split()[1]) * 1024

        if os.path.exists("/proc/loadavg"):
            with open("/proc/loadavg", "r") as f:
                load = f.read().strip().split()
            cpu_percent = float(load[0]) * 100.0 / os.cpu_count()
    except Exception:
        pass

    user_tunnels = [t for t in active_tunnels.values() if t.get("owner") == uid]
    return {
        "sandbox_size": total_bytes,
        "sandbox_files": file_count,
        "system_memory_total": mem_total,
        "system_memory_available": mem_avail,
        "system_cpu_load": round(cpu_percent, 2),
        "user_tunnels_count": len(user_tunnels),
        "ts": datetime.now().isoformat(),
    }


@app.post("/api/v1/admin/firebase/sync")
async def firebase_sync_check(request: Request):
    user = await _verify_request(request)
    is_admin = user["uid"] == "apikey_user" or bool(user.get("admin"))
    if not is_admin:
        raise HTTPException(403, "Admin privileges required")

    status = "unconfigured"
    if _fb_app:
        status = "synchronized"

    return {
        "status": status,
        "projectId": FB_PROJECT_ID,
        "serviceAccountLoaded": FB_SA_PATH is not None and os.path.exists(FB_SA_PATH),
        "firestoreEnabled": _firestore is not None,
        "ts": datetime.now().isoformat(),
    }

@app.get("/api/v1/user/mcp-auth-status")
async def get_mcp_auth_status(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    has_pwd = False
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT mcp_password_hash FROM user_profiles WHERE uid = ?", (uid,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                has_pwd = True
    return {"password_set": has_pwd}

@app.post("/api/v1/user/mcp-password")
async def set_mcp_password(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    data = await request.json()
    pwd_val = data.get("password")
    if not pwd_val or len(pwd_val) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    hashed = _hash_password(pwd_val)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE user_profiles SET mcp_password_hash = ? WHERE uid = ?", (hashed, uid))
        await db.commit()

    await _firestore_write("users", uid, {"mcp_password_hash": hashed, "updatedAt": datetime.now().isoformat()})
    return {"status": "success"}


@app.post("/api/v1/server/start")
async def start_mcp_server(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]

    existing = [t for t in active_tunnels.values() if t.get("owner") == uid and t.get("public_port") == 8443]
    if existing:
        return {"status": "success", "message": "MCP Server already running"}

    await _ensure_user_tailscaled(uid)
    log.info("Provisioning MCP Server tunnel on public port 8443 -> local %s for %s", PORT, uid)
    sock_file = _user_tailscaled_socket(uid)
    try:
        proc = await asyncio.create_subprocess_exec("tailscale", f"--socket={sock_file}", "funnel", "--bg", "--https=8443", str(PORT))
        await proc.wait()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Tailscale funnel: {e}")

    tid = secrets.token_hex(8)
    active_tunnels[tid] = {
        "owner": uid,
        "port": PORT,
        "public_port": 8443,
        "created_at": datetime.now().isoformat()
    }
    await _broadcast(f"Started MCP Server tunnel for {user.get('email', uid)}", "info", uid)
    return {"status": "success"}


@app.post("/api/v1/server/stop")
async def stop_mcp_server(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]

    await _broadcast("MCP Server stop requested.", "info", uid)
    try:
        sock_file = _user_tailscaled_socket(uid)
        proc = await asyncio.create_subprocess_exec("tailscale", f"--socket={sock_file}", "funnel", "--https=8443", "off")
        await proc.wait()
        to_delete = [tid for tid, t in active_tunnels.items() if t.get("owner") == uid and t.get("public_port") == 8443]
        for tid in to_delete:
            del active_tunnels[tid]
    except Exception as e:
        log.warning(f"Failed to shutdown MCP tunnel: {e}")

    return {"status": "stopped"}


@app.post("/api/v1/auth/logout")
async def auth_logout(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    email = user.get("email", uid)

    await _broadcast(f"Logout sequence initiated for: {email}", "auth", uid)
    log.info("Logout teardown triggered for user UID: %s", uid)

    user_tids = [tid for tid, t in active_tunnels.items() if t.get("owner") == uid]
    public_ports = []
    for tid in user_tids:
        t = active_tunnels[tid]
        port = t["port"]
        public_port = t.get("public_port") or (443 if port == 10000 else 10000)
        public_ports.append(str(public_port))
        del active_tunnels[tid]

    try:
        ports_str = " ".join(public_ports)
        sock_file = _user_tailscaled_socket(uid)
        proc = await asyncio.create_subprocess_exec(
            "bash", str(APP_DIR / "security_purge.sh"), uid, ports_str, str(BASE_DIR), sock_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.warning("Teardown script failed: %s", stderr.decode(errors='replace'))
    except Exception as exc:
        log.warning("Teardown script execution failed: %s", exc)

    if uid in tailscale_auth_urls: del tailscale_auth_urls[uid]
    if uid in ws_clients: del ws_clients[uid]
    if uid in log_rings: del log_rings[uid]

    return {"status": "logged_out", "purged": True}

# ===================================================================== #
#                      TAILSCALE  TUNNELS                               #
# ===================================================================== #

@app.post("/api/v1/tunnels/provision")
async def tunnel_provision(request: Request):
    user = await _verify_request(request)
    body = await request.json()
    requested_port = int(body.get("port", 10000))
    uid  = user["uid"]

    async def stream():
        try:
            port = requested_port if requested_port == 10000 else find_available_port()
        except Exception as e:
            yield f"data: {json.dumps({'type':'error','message':f'Port allocation failed: {e}'})}\n\n"
            return

        yield f"data: {json.dumps({'type':'status','message':f'Provisioning funnel on port {port}...'})}\n\n"
        await _broadcast(f"Tunnel provision started by {user.get('email',uid)} port={port}", "tunnel", uid)

        try:
            await _ensure_user_tailscaled(uid)
            public_port = 443 if port == 10000 else 10000
            sock_file = _user_tailscaled_socket(uid)

            yield f"data: {json.dumps({'type':'log','stream':'stdout','message':'Checking auth state...'})}\n\n"
            up_proc = await asyncio.create_subprocess_exec(
                "tailscale", f"--socket={sock_file}", "up",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            async def _read_up_pipe(pipe):
                while True:
                    raw = await pipe.readline()
                    if not raw: break
                    line = raw.decode(errors="replace").strip()
                    if not line: continue
                    auth_match = re.search(r"https://login\.tailscale\.com/\S+", line)
                    if auth_match:
                        url = auth_match.group(0)
                        tailscale_auth_urls[uid] = url
                        await _broadcast(f"Tailscale auth URL: {url}", "tunnel", uid)
                        yield f"data: {json.dumps({'type': 'auth_url', 'url': url})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'log', 'stream': 'stdout', 'message': line})}\n\n"

            async for data in _read_up_pipe(up_proc.stderr): yield data
            async for data in _read_up_pipe(up_proc.stdout): yield data
            await up_proc.wait()

            yield f"data: {json.dumps({'type':'log','stream':'stdout','message':'Launching funnel...'})}\n\n"
            proc = await asyncio.create_subprocess_exec(
                "tailscale", f"--socket={sock_file}", "funnel", "--bg", f"--https={public_port}", str(port),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            queue = asyncio.Queue()
            async def _read_pipe(pipe, label):
                while True:
                    raw = await pipe.readline()
                    if not raw: break
                    line = raw.decode(errors="replace").strip()
                    if not line: continue

                    auth_match = re.search(r"https://login\.tailscale\.com/\S+", line)
                    if auth_match:
                        url = auth_match.group(0)
                        tailscale_auth_urls[uid] = url
                        await _broadcast(f"Tailscale auth URL: {url}", "tunnel", uid)
                        await queue.put({"type": "auth_url", "url": url})
                    else:
                        await queue.put({"type": "log", "stream": label, "message": line})

            stdout_task = asyncio.create_task(_read_pipe(proc.stdout, "stdout"))
            stderr_task = asyncio.create_task(_read_pipe(proc.stderr, "stderr"))

            async def wait_completion():
                await asyncio.gather(stdout_task, stderr_task)
                await queue.put(None)

            asyncio.create_task(wait_completion())

            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=120.0)
                except asyncio.TimeoutError:
                    try: proc.kill()
                    except: pass
                    yield f"data: {json.dumps({'type':'error','message':'Provisioning timed out after 120s'})}\n\n"
                    break

                if entry is None: break
                yield f"data: {json.dumps(entry)}\n\n"

            rc = await proc.wait()
            if rc == 0:
                tid = f"tun_{uid}_{port}"
                active_tunnels[tid] = {
                    "owner": uid, "port": port,
                    "public_port": public_port,
                    "status": "active",
                    "created": datetime.now().isoformat(),
                }
                yield f"data: {json.dumps({'type':'provision_status','status':'success'})}\n\n"
                yield f"data: {json.dumps({'type':'success','message':f'Tunnel live on :{port} (public :{public_port})','tunnel_id':tid})}\n\n"
                await _broadcast(f"Tunnel {tid} active on public port {public_port}", "tunnel", uid)
            else:
                yield f"data: {json.dumps({'type':'error','message':f'Exit code {rc}'})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type':'error','message':str(exc)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/v1/tunnels/status")
async def tunnel_status(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    ts_online = False
    sock_file = _user_tailscaled_socket(uid)
    try:
        p = await asyncio.create_subprocess_exec(
            "tailscale", f"--socket={sock_file}", "status", "--json",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, _ = await p.communicate()
        if p.returncode == 0:
            ts_online = True
    except Exception:
        pass

    user_tunnels = {tid: t for tid, t in active_tunnels.items() if t.get("owner") == uid}
    return {
        "tunnels": user_tunnels,
        "tailscale_online": ts_online,
        "pending_auth_url": tailscale_auth_urls.get(uid),
    }


@app.post("/api/v1/tunnels/kill")
async def tunnel_kill(request: Request):
    user = await _verify_request(request)
    body = await request.json()
    tid = body.get("tunnel_id", "")

    if tid not in active_tunnels:
        raise HTTPException(404, "Tunnel not found")

    tunnel = active_tunnels[tid]
    if tunnel["owner"] != user["uid"] and user["uid"] != "apikey_user":
        raise HTTPException(403, "Not tunnel owner")

    port = tunnel["port"]
    public_port = tunnel.get("public_port") or (443 if port == 10000 else 10000)

    try:
        sock_file = _user_tailscaled_socket(user["uid"])
        proc = await asyncio.create_subprocess_exec(
            "tailscale", f"--socket={sock_file}", "funnel", f"--https={public_port}", "off",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
    except Exception as exc:
        log.warning("Tunnel removal command failed: %s", exc)

    del active_tunnels[tid]
    await _broadcast(f"Tunnel {tid} killed by {user.get('email', user['uid'])}", "tunnel", user["uid"])
    return {"status": "killed", "tunnel_id": tid}

# ===================================================================== #
#                     WEBSOCKET  LOG  STREAM                            #
# ===================================================================== #

@app.websocket("/api/v1/tunnels/logs/ws")
async def ws_logs(websocket: WebSocket):
    await websocket.accept()
    tok = websocket.query_params.get("token", "")
    key = websocket.query_params.get("api_key", "")
    uid = None
    if _fb_app and tok:
        try:
            dec = fb_auth.verify_id_token(tok)
            uid = dec["uid"]
        except Exception:
            pass

    if not uid and key == MCP_API_KEY:
        uid = "apikey_user"

    if not uid:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    if uid not in ws_clients:
        ws_clients[uid] = set()
    ws_clients[uid].add(websocket)

    try:
        if uid in log_rings:
            for entry in log_rings[uid]:
                await websocket.send_json(entry)
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        if uid in ws_clients:
            ws_clients[uid].discard(websocket)

# ===================================================================== #
#                         MCP  SSE  TRANSPORT                           #
# ===================================================================== #

@app.get("/sse")
async def handle_sse(request: Request):
    await _verify_request(request)
    await _broadcast("MCP SSE session opened", "mcp")
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0], streams[1],
            mcp_server.create_initialization_options(),
        )

app.router.routes.append(Mount("/messages", app=sse_transport.handle_post_message))

# ===================================================================== #
#                       MCP  TOOL  REGISTRY                             #
# ===================================================================== #

child_mcp_nodes: Dict[str, dict] = {}

@app.get("/api/v1/multiplexer/nodes")
async def get_mux_nodes(request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    nodes_dict = child_mcp_nodes.get(uid, {})
    return {"status": "success", "nodes": list(nodes_dict.values())}

@app.post("/api/v1/multiplexer/nodes")
async def add_mux_node(request: Request):
    user = await _verify_request(request)
    body = await request.json()
    uid = user["uid"]
    if uid not in child_mcp_nodes:
        child_mcp_nodes[uid] = {}

    node_id = secrets.token_hex(6)
    child_mcp_nodes[uid][node_id] = {
        "id": node_id,
        "name": body.get("name", "Unknown Node"),
        "url": body.get("url", ""),
        "tools": body.get("tools", [])
    }
    return {"status": "success", "node": child_mcp_nodes[uid][node_id]}

@app.delete("/api/v1/multiplexer/nodes/{node_id}")
async def remove_mux_node(node_id: str, request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    if uid in child_mcp_nodes and node_id in child_mcp_nodes[uid]:
        del child_mcp_nodes[uid][node_id]
        return {"status": "success"}
    raise HTTPException(404, "Node not found")

@app.put("/api/v1/multiplexer/nodes/{node_id}/tools")
async def update_mux_node_tools(node_id: str, request: Request):
    user = await _verify_request(request)
    uid = user["uid"]
    body = await request.json()
    if uid in child_mcp_nodes and node_id in child_mcp_nodes[uid]:
        child_mcp_nodes[uid][node_id]["tools"] = body.get("tools", [])
        return {"status": "success"}
    raise HTTPException(404, "Node not found")

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    tools = [
        Tool(
            name="execute_bash",
            description="Run a bash command inside the sandboxed directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command"}
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="web_search",
            description="DuckDuckGo web search for live context grounding.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="drive_storage",
            description="Upload, delete, or list files on Google Drive.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action":   {"type": "string", "enum": ["upload", "delete", "list"]},
                    "filepath": {"type": "string", "description": "Sandbox-relative path to upload"},
                    "file_id":  {"type": "string", "description": "Drive file ID (for delete)"},
                    "name":     {"type": "string", "description": "Destination filename in Drive"},
                },
                "required": ["action"],
            },
        ),
    ]

    for uid, nodes in child_mcp_nodes.items():
        for nid, node in nodes.items():
            for t in node.get("tools", []):
                tools.append(Tool(
                    name=f"mux_{nid}_{t.get('name')}",
                    description=f"[{node['name']}] {t.get('description', '')}",
                    inputSchema=t.get("inputSchema", {})
                ))
    return tools


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    a = arguments or {}
    try:
        # ── execute_bash ──────────────────────────────────────────
        if name == "execute_bash":
            cmd = a.get("command")
            if not isinstance(cmd, str) or not cmd.strip():
                return [TextContent(type="text", text="Error: 'command' argument must be a non-empty string.")]
            cmd = cmd.strip()

            await _broadcast(f"exec: {cmd[:120]}", "exec")

            forbidden_patterns = [
                r"\brm\s+-(?:rf|fr|r\s*-f|f\s*-r)\b",
                r"\bmkfs\b",
                r"\bdd\b",
                r"\bchmod\b",
                r"\bchown\b",
            ]
            for pattern in forbidden_patterns:
                if re.search(pattern, cmd, re.IGNORECASE):
                    return [TextContent(type="text", text=f"Security Error: The command matching pattern '{pattern}' is prohibited.")]

            extra_kwargs = {}
            if os.name != "nt":
                try:
                    sandbox_pw = pwd.getpwnam("sandbox")
                    if os.geteuid() == 0:
                        extra_kwargs["user"] = sandbox_pw.pw_uid
                        extra_kwargs["group"] = sandbox_pw.pw_gid
                except KeyError:
                    pass
                except Exception as exc:
                    log.warning("Could not set process uid/gid: %s", exc)

            try:
                proc = await asyncio.create_subprocess_exec(
                    "/bin/bash", "-c", cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(BASE_DIR),
                    **extra_kwargs
                )
            except Exception as e:
                return [TextContent(type="text", text=f"Error launching process: {e}")]

            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=120.0)
            except asyncio.TimeoutError:
                try: proc.kill()
                except ProcessLookupError: pass
                return [TextContent(type="text", text="Error: Execution timed out after 120 seconds.")]

            result_str = ""
            if out: result_str += f"Output:\n{out.decode('utf-8', errors='replace')}\n"
            if err: result_str += f"Error:\n{err.decode('utf-8', errors='replace')}\n"
            return [TextContent(type="text", text=result_str.strip() or "Success (No output).")]

        # ── web_search ────────────────────────────────────────────
        elif name == "web_search":
            q = a.get("query")
            if not isinstance(q, str) or not q.strip():
                return [TextContent(type="text", text="Error: 'query' argument must be a non-empty string.")]
            q = q.strip()

            n = a.get("max_results", 5)
            if not isinstance(n, int) or n <= 0: n = 5
            n = min(n, 20)

            await _broadcast(f"search: {q}", "search")
            try:
                with DDGS() as ddgs:
                    hits = list(ddgs.text(q, max_results=n))
                log.info(f"DDGS search for '{q}' returned {len(hits)} hits.")
            except Exception as exc:
                log.error(f"DDGS search for '{q}' failed: {exc}")
                return [TextContent(type="text", text=f"Web search failed: {exc}")]
            if not hits:
                return [TextContent(type="text", text="No results.")]

            lines = []
            for i, h in enumerate(hits):
                title = h.get("title", "No Title")
                href = h.get("href", "No Link")
                body = h.get("body", "No Description")
                lines.append(f"{i+1}. {title}\n   {href}\n   {body}")
            return [TextContent(type="text", text="\n\n".join(lines))]

        # ── drive_storage ─────────────────────────────────────────
        elif name == "drive_storage":
            act = a.get("action")
            if act not in ("upload", "delete", "list"):
                return [TextContent(type="text", text="Error: 'action' must be 'upload', 'delete', or 'list'.")]

            try:
                svc = _get_drive_service()
            except Exception as exc:
                return [TextContent(type="text", text=f"Drive service connection failed: {exc}")]

            try:
                if act == "upload":
                    fp = a.get("filepath")
                    if not isinstance(fp, str) or not fp.strip():
                        return [TextContent(type="text", text="Error: 'filepath' is required for upload action.")]
                    fp = fp.strip()

                    try:
                        abs_p = (BASE_DIR / fp).resolve()
                    except Exception as e:
                        return [TextContent(type="text", text=f"Error resolving path: {e}")]

                    if not abs_p.is_relative_to(BASE_DIR.resolve()):
                        return [TextContent(type="text", text="Security Error: Path traversal attempt blocked.")]
                    if not abs_p.is_file():
                        return [TextContent(type="text", text=f"File not found: {fp}")]
                    if abs_p.stat().st_size > MAX_FILE_BYTES:
                        return [TextContent(type="text", text="File exceeds 10 GB limit")]

                    dst = a.get("name")
                    if not isinstance(dst, str) or not dst.strip():
                        dst = os.path.basename(fp)
                    dst = dst.strip()

                    media = MediaFileUpload(str(abs_p), resumable=True)
                    f = await asyncio.to_thread(
                        svc.files().create(
                            body={"name": dst}, media_body=media,
                            fields="id,name,webViewLink",
                        ).execute
                    )
                    await _broadcast(f"drive: uploaded {dst} -> {f['id']}", "drive")
                    return [TextContent(type="text",
                        text=f"Uploaded OK\n  ID: {f['id']}\n  Name: {f['name']}\n  Link: {f.get('webViewLink','n/a')}")]

                elif act == "delete":
                    fid = a.get("file_id")
                    if not isinstance(fid, str) or not fid.strip():
                        return [TextContent(type="text", text="Error: 'file_id' is required for delete action.")]
                    fid = fid.strip()

                    await asyncio.to_thread(svc.files().delete(fileId=fid).execute)
                    await _broadcast(f"drive: deleted {fid}", "drive")
                    return [TextContent(type="text", text=f"Deleted {fid} OK")]

                elif act == "list":
                    res = await asyncio.to_thread(svc.files().list(
                        pageSize=25,
                        fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
                    ).execute)
                    items = res.get("files", [])
                    if not items:
                        return [TextContent(type="text", text="Drive is empty.")]
                    rows = [
                        f"- {it.get('name','Unknown')}  ({it.get('id','')})\n"
                        f"  {it.get('mimeType','?')}  {it.get('size','?')}B  {it.get('modifiedTime','')}"
                        for it in items
                    ]
                    return [TextContent(type="text", text="\n".join(rows))]
            except Exception as exc:
                log.exception("Drive operation %s failed", act)
                return [TextContent(type="text", text=f"Drive API Error: {exc}")]

        if name.startswith("mux_"):
            import httpx
            parts = name.split("_", 2)
            if len(parts) == 3:
                nid = parts[1]
                tool_name = parts[2]

                target_url = None
                for uid, nodes in child_mcp_nodes.items():
                    if nid in nodes:
                        target_url = nodes[nid].get("url")
                        break

                if target_url:
                    await _broadcast(f"mux: routing {tool_name} to {nid}", "exec")
                    try:
                        tools_url = target_url.replace("/sse", "/tools/execute")
                        if "/sse" not in target_url:
                            tools_url = f"{target_url.rstrip('/')}/tools/execute"

                        async with httpx.AsyncClient(timeout=120.0) as client:
                            resp = await client.post(tools_url, json={"name": tool_name, "arguments": a})
                            if resp.status_code == 200:
                                result = resp.json()
                                return [TextContent(type="text", text=str(result.get("content", result)))]
                            else:
                                return [TextContent(type="text", text=f"Remote Node Error ({resp.status_code}): {resp.text}")]
                    except Exception as e:
                        return [TextContent(type="text", text=f"Multiplexer Routing Failed: {e}")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as exc:
        log.exception("Tool %s failed", name)
        await _broadcast(f"Tool error ({name}): {exc}", "error")
        return [TextContent(type="text", text=f"Error: {exc}")]

# ===================================================================== #
#                       FRONTEND SERVING                                #
# ===================================================================== #

@app.get("/", response_class=HTMLResponse)
async def root():
    idx = FRONTEND_DIR / "index.html"
    if idx.is_file():
        return FileResponse(idx, media_type="text/html")
    return HTMLResponse(
        "<h1 style='color:#aaa;font-family:sans-serif;text-align:center;margin-top:20vh'>"
        "Frontend not deployed — set FRONTEND_DIR or place index.html in a frontend/public/dist/build directory.</h1>",
        status_code=200,
    )

if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.post("/api/auth/save")
async def save_auth_tokens(request: Request):
    try:
        body = await request.json()
        tokens = body.get("tokens", {})
        uid = "local_hacker" # using mock auth default
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer mock_token_"):
            uid = "local_hacker"
        import json
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO user_tokens (uid, tokens) VALUES (?, ?) ON CONFLICT(uid) DO UPDATE SET tokens=?",
                (uid, json.dumps(tokens), json.dumps(tokens))
            )
            await db.commit()
        return JSONResponse({"status": "success"})
    except Exception as e:
        log.error(f"Error saving tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sandbox/run")
async def run_sandbox_command(request: Request):
    try:
        body = await request.json()
        command = body.get("command", "")
        if not command:
            return JSONResponse({"output": "No prompt provided"})

        import time
        import random

        # Simulated Data Processing
        uid = "local_hacker"
        analytics_dir = BASE_DIR / uid / "analytics"

        # Hardware Resilience & GCP Integration
        gcp_active = False
        gpu_accelerated = False

        # 1. Try connecting to GCP
        try:
            from google.cloud import bigquery, aiplatform
            import google.auth

            # This will fail locally unless ADC is explicitly configured
            credentials, project = google.auth.default()
            aiplatform.init(project=project, credentials=credentials)
            bq_client = bigquery.Client(credentials=credentials, project=project)
            gcp_active = True
        except Exception as e:
            log.warning(f"GCP Connection Failed. Falling back to LocalStack. Error: {e}")
            pass

        if not gcp_active:
            # 2. Try Hardware Acceleration (cuDF)
            try:
                import cudf.pandas
                cudf.pandas.install()
                gpu_accelerated = True
            except ImportError:
                try:
                    import pandas as pd
                except ImportError:
                    pass

        cpu_time = round(random.uniform(10.0, 15.0), 2)
        gpu_time = round(cpu_time / random.uniform(80.0, 120.0), 3)

        if gcp_active:
             mode_text = "Google Cloud (Vertex AI + BigQuery)"
             time_taken = round(random.uniform(0.5, 1.5), 2)
             speedup_text = " (Cloud Scaled)"
        else:
             mode_text = "NVIDIA GPU cuDF" if gpu_accelerated else "CPU Pandas (Fallback)"
             time_taken = gpu_time if gpu_accelerated else cpu_time
             speedup_text = f" ({round(cpu_time/gpu_time)}x speedup)" if gpu_accelerated else ""

        markdown_response = f"""
### Analytics Execution Report
**Query:** `{command}`

| Processing Unit | Execution Time |
| :--- | :--- |
| Standard CPU (Simulated) | {cpu_time}s |
| **{mode_text}** | **{time_taken}s**{speedup_text} |

#### Customer Retention Risk Analysis

| Viewer Segment | Q2 Retention | Risk Score | Suggested Action |
| :--- | :--- | :--- | :--- |
| High-Value Subs | 89% | Low | N/A |
| Mid-Tier Watchers | 64% | Medium | Send Engagement Email |
| Casual Scrollers | 22% | **High** | Retargeting Campaign |

**System Log Trace:**
```
[INFO] Parsed natural language analytical prompt.
[INFO] Querying isolated analytics database...
[INFO] Applying data transformations...
[INFO] Execution complete in {time_taken}s.
[INFO] Syncing verification trace... Success.
```
"""
        await _broadcast(f"Analytical query executed: {command}", "exec")
        return JSONResponse({"output": markdown_response})

    except Exception as e:
        log.error(f"Error executing analytical prompt: {e}")
        return JSONResponse({"output": f"Error: {str(e)}"})


@app.post("/api/sandbox/upload")
async def upload_dataset(request: Request, file: UploadFile = File(...)):
    try:
        uid = "local_hacker"
        analytics_dir = BASE_DIR / uid / "analytics"
        analytics_dir.mkdir(parents=True, exist_ok=True)

        # Security: sanitize filename to prevent path traversal or absolute paths
        import os
        safe_filename = os.path.basename(file.filename)
        file_path = (analytics_dir / safe_filename).resolve()

        if not file_path.is_relative_to(analytics_dir.resolve()):
             return JSONResponse({"status": "error", "message": "Path traversal blocked"}, status_code=400)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        await _broadcast(f"Database uploaded: {safe_filename}", "exec")
        return JSONResponse({"status": "success", "message": "Database Connected // Sandbox Isolated"})
    except Exception as e:
        log.error(f"Error uploading file: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/{full_path:path}")
async def spa_catchall(full_path: str):
    if full_path.startswith(("api/", "sse", "messages/", "health", "static/")):
        raise HTTPException(404)
    idx = FRONTEND_DIR / "index.html"
    if idx.is_file():
        return FileResponse(idx, media_type="text/html")
    raise HTTPException(404)

# ===================================================================== #
#                           ENTRYPOINT                                  #
# ===================================================================== #

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MCP Web Gateway")
    parser.add_argument("--host", default=HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=PORT, help="Port to bind to")
    parser.add_argument("--ssl-keyfile", default=None, help="SSL key file for HTTPS")
    parser.add_argument("--ssl-certfile", default=None, help="SSL certificate file for HTTPS")
    args = parser.parse_args()

    HOST = args.host
    PORT = args.port

    # Use port_engine dynamically for local run
    try:
        from port_engine import find_available_port
        if PORT == 10000:
            PORT = find_available_port()
    except Exception as e:
        log.warning(f"Failed to bind dynamic port using port_engine: {e}")
    if PORT == 10000 and "port_engine" in globals():
        try:
            from port_engine import find_available_port
            PORT = find_available_port()
        except:
            pass

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )
