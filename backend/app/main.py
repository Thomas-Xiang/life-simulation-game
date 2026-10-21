import hashlib
import importlib
import json
import os
import secrets
import sqlite3
import time

from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Required application modules
# ---------------------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
BASE = APP_DIR.parent


def load_required_module(name: str):
    """
    Import an application module with a useful startup error.

    Do not silently fall back to simulation.py: doing so would restore the
    old question scheduler and omit the new partner/law/family rules.
    """
    module_path = APP_DIR / f"{name}.py"

    if not module_path.is_file():
        raise RuntimeError(
            f"Required file is missing: {module_path}\n"
            f"Create backend/app/{name}.py using the corresponding update. "
            f"Make sure the filename is exactly '{name}.py', "
            f"not '{name}.py.txt'."
        )

    try:
        return importlib.import_module(f".{name}", package=__package__)
    except SyntaxError as exc:
        raise RuntimeError(
            f"Syntax error in {exc.filename}, line {exc.lineno}: {exc.msg}\n"
            "Use plain Python code, without HTML tags or HTML entities. "
            "In the earlier rules.py snippet, replace accidental '\\]' "
            "sequences with ']'."
        ) from exc
    except ImportError as exc:
        raise RuntimeError(
            f"Could not import {module_path}: {exc}\n"
            "Check the full traceback below for a missing dependency "
            "or a circular import."
        ) from exc


sim = load_required_module("rules")
births_module = load_required_module("births")

random_home = births_module.random_home


# ---------------------------------------------------------------------------
# Mortality data
# ---------------------------------------------------------------------------

MORTALITY_PATH = BASE / "data" / "mortality.json"

if not MORTALITY_PATH.is_file():
    raise RuntimeError(
        f"Mortality data is missing: {MORTALITY_PATH}"
    )

try:
    MORT = json.loads(
        MORTALITY_PATH.read_text(encoding="utf-8")
    )
except (OSError, json.JSONDecodeError) as exc:
    raise RuntimeError(
        f"Could not read mortality data: {MORTALITY_PATH}"
    ) from exc

for category in ("male", "female"):
    probabilities = MORT.get(category)

    if (
        not isinstance(probabilities, list)
        or len(probabilities) != 120
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 1
            for value in probabilities
        )
    ):
        raise RuntimeError(
            f"Invalid mortality data for '{category}'. "
            "Expected 120 probabilities between 0 and 1."
        )


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def database_path() -> Path:
    configured = (
        os.getenv("LIFE_ATLAS_V2_DB_PATH")
        or os.getenv("DB_PATH")
    )

    if configured:
        return Path(configured).expanduser().resolve()

    return BASE / "var" / "states-v2.db"


@contextmanager
def db():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(path),
        timeout=10,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize():
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS lives (
                id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                seed TEXT NOT NULL,
                state TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memorials (
                id TEXT PRIMARY KEY,
                life_id TEXT UNIQUE REFERENCES lives(id),
                state TEXT,
                age INTEGER,
                message TEXT,
                approved INTEGER DEFAULT 0,
                candles INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS candles (
                memorial_id TEXT REFERENCES memorials(id),
                voter TEXT,
                PRIMARY KEY (memorial_id, voter)
            );
            """
        )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    initialize()
    yield


app = FastAPI(
    title="Life Atlas: State Chapters",
    version="2.1.0",
    lifespan=lifespan,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# Request limits
# ---------------------------------------------------------------------------

MAX_BODY_BYTES = 16_384
REQUESTS_PER_MINUTE = 1_200

request_times = defaultdict(deque)
request_lock = Lock()


@app.middleware("http")
async def request_limits(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    if request.method in {"POST", "PUT", "PATCH"}:
        chunks = []
        total_bytes = 0

        async for chunk in request.stream():
            total_bytes += len(chunk)

            if total_bytes > MAX_BODY_BYTES:
                return JSONResponse(
                    {"detail": "Request too large"},
                    status_code=413,
                )

            chunks.append(chunk)

        # Preserve the bounded body for downstream request parsing.
        request._body = b"".join(chunks)

    now = time.monotonic()
    client_ip = (
        request.client.host
        if request.client
        else "unknown"
    )

    with request_lock:
        expired_keys = [
            key
            for key, timestamps in request_times.items()
            if not timestamps or now - timestamps[-1] > 60
        ]

        for key in expired_keys:
            del request_times[key]

        timestamps = request_times[client_ip]

        while timestamps and now - timestamps[0] > 60:
            timestamps.popleft()

        if len(timestamps) >= REQUESTS_PER_MINUTE:
            return JSONResponse(
                {"detail": "Slow down and retry shortly"},
                status_code=429,
                headers={"Retry-After": "60"},
            )

        timestamps.append(now)

    response = await call_next(request)

    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Birth(Strict):
    # Starting state is drawn on the server.
    # The frontend should send an empty JSON object: {}.
    pass


class Step(Strict):
    version: int = Field(ge=0)


class Choice(Step):
    question_id: str = Field(
        min_length=1,
        max_length=150,
    )
    option_id: str = Field(
        min_length=1,
        max_length=50,
    )


class Memorial(Strict):
    message: str = Field(
        default="",
        max_length=500,
    )


# ---------------------------------------------------------------------------
# Authentication and state helpers
# ---------------------------------------------------------------------------

def bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""

    scheme, separator, token = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer":
        return ""

    return token.strip()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def owner(connection, life_id: str, authorization: str | None):
    token = bearer_token(authorization)

    row = connection.execute(
        "SELECT * FROM lives WHERE id = ?",
        (life_id,),
    ).fetchone()

    if (
        not token
        or row is None
        or not secrets.compare_digest(
            row["token_hash"],
            token_hash(token),
        )
    ):
        raise HTTPException(
            status_code=404,
            detail="Life not found",
        )

    life = json.loads(row["state"])

    if life.get("schema_version") != 2:
        raise HTTPException(
            status_code=409,
            detail=(
                "This save uses an older schema. "
                "Use its original app to view it and start a new journey."
            ),
        )

    # Supply defaults for additional v2.1 fields.
    # This does not reconstruct decisions missing from older journeys.
    sim.ensure(life)

    return row, life


def payload(life):
    current_question = sim.question(life)

    return {
        "life": life,
        "question": current_question,
        "balance": sim.balance(life),
        "projection": sim.quote(
            life,
            life["state"],
            life["housing"],
        ),
    }


def save(connection, life):
    connection.execute(
        "UPDATE lives SET state = ? WHERE id = ?",
        (
            json.dumps(life),
            life["id"],
        ),
    )


def require_version(life, expected_version: int):
    if life["version"] != expected_version:
        raise HTTPException(
            status_code=409,
            detail="Life changed. Reload the saved journey.",
        )


# ---------------------------------------------------------------------------
# Health and state profiles
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "ready",
        "edition": "state-chapters-v2.1",
        "states": len(sim.STATES),
        "financial_data": "synthetic game scenarios",
        "birth_weights_year": 2024,
        "birth_weights_basis": "final resident birth counts",
        "mortality": MORT.get("version", "unknown"),
    }


@app.get("/api/states")
def states():
    return list(sim.STATES.values())


# ---------------------------------------------------------------------------
# Journey creation and loading
# ---------------------------------------------------------------------------

@app.post("/api/lives", status_code=201)
def born(body: Birth):
    life_id = str(uuid4())
    token = secrets.token_urlsafe(32)
    seed = secrets.token_hex(32)

    home_state = random_home(seed)

    if home_state not in sim.STATES:
        raise HTTPException(
            status_code=500,
            detail="Birth weights reference an unknown state.",
        )

    life = sim.new_life(
        home_state,
        seed,
        life_id,
    )
    life["schema_version"] = 2

    # Explicit game assumption for selecting a mortality-table category.
    life["sex"] = (
        "male"
        if sim.rng(seed, "sex").random() < 0.5
        else "female"
    )

    result = payload(life)

    with db() as connection:
        connection.execute(
            "INSERT INTO lives VALUES (?, ?, ?, ?)",
            (
                life_id,
                token_hash(token),
                seed,
                json.dumps(life),
            ),
        )

    return {
        **result,
        "token": token,
    }


@app.get("/api/lives/{life_id}")
def load(
    life_id: str,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        _, life = owner(
            connection,
            life_id,
            authorization,
        )

        return payload(life)


# ---------------------------------------------------------------------------
# Annual progression and choices
# ---------------------------------------------------------------------------

@app.post("/api/lives/{life_id}/step")
def step(
    life_id: str,
    body: Step,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")

        row, life = owner(
            connection,
            life_id,
            authorization,
        )

        require_version(life, body.version)

        try:
            sim.advance(
                life,
                row["seed"],
                MORT,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

        result = payload(life)
        save(connection, life)

        return result


@app.post("/api/lives/{life_id}/choice")
def choice(
    life_id: str,
    body: Choice,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")

        _, life = owner(
            connection,
            life_id,
            authorization,
        )

        require_version(life, body.version)

        try:
            sim.choose(
                life,
                body.question_id,
                body.option_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=409,
                detail=str(exc),
            ) from exc

        result = payload(life)
        save(connection, life)

        return result


# ---------------------------------------------------------------------------
# Comparisons and survival chart
# ---------------------------------------------------------------------------

@app.get("/api/lives/{life_id}/compare")
def compare(
    life_id: str,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        _, life = owner(
            connection,
            life_id,
            authorization,
        )

    results = []

    for code in sim.STATES:
        family_housing_available = (
            code == life["home_state"]
            and life["family"]["housing"]
        )

        housing = (
            "parents"
            if family_housing_available
            else "shared"
        )

        results.append(
            sim.quote(
                life,
                code,
                housing,
            )
        )

    return results


@app.get("/api/lives/{life_id}/survival")
def survival(
    life_id: str,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        _, life = owner(
            connection,
            life_id,
            authorization,
        )

    probability = 1.0

    points = [
        {
            "age": 0,
            "survival": probability,
        }
    ]

    for age, annual_probability in enumerate(MORT[life["sex"]]):
        probability *= 1 - annual_probability

        points.append({
            "age": age + 1,
            "survival": probability,
        })

    return points


# ---------------------------------------------------------------------------
# Export and deletion
# ---------------------------------------------------------------------------

@app.get("/api/lives/{life_id}/export")
def export(
    life_id: str,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        _, life = owner(
            connection,
            life_id,
            authorization,
        )

    return {
        "schema_version": 2,
        "rules_version": "2.1",
        "money_unit": "USD cents",
        "financial_basis": "synthetic game scenarios",
        "life": life,
    }


@app.delete(
    "/api/lives/{life_id}",
    status_code=204,
    response_class=Response,
)
def delete(
    life_id: str,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")

        owner(
            connection,
            life_id,
            authorization,
        )

        connection.execute(
            """
            DELETE FROM candles
            WHERE memorial_id IN (
                SELECT id
                FROM memorials
                WHERE life_id = ?
            )
            """,
            (life_id,),
        )

        connection.execute(
            "DELETE FROM memorials WHERE life_id = ?",
            (life_id,),
        )

        connection.execute(
            "DELETE FROM lives WHERE id = ?",
            (life_id,),
        )

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Memorial submissions and public wall
# ---------------------------------------------------------------------------

@app.post(
    "/api/lives/{life_id}/memorial",
    status_code=201,
)
def memorial(
    life_id: str,
    body: Memorial,
    authorization: str | None = Header(default=None),
):
    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")

        _, life = owner(
            connection,
            life_id,
            authorization,
        )

        if life.get("end_reason") != "death":
            raise HTTPException(
                status_code=409,
                detail="Only sampled deaths can be memorialized.",
            )

        existing = connection.execute(
            "SELECT id FROM memorials WHERE life_id = ?",
            (life_id,),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="A memorial has already been submitted.",
            )

        connection.execute(
            """
            INSERT INTO memorials (
                id,
                life_id,
                state,
                age,
                message
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                life_id,
                life["state"],
                life["age"],
                body.message.strip(),
            ),
        )

    return {
        "status": "pending_moderation",
    }


@app.get("/api/memorials")
def wall():
    with db() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                state,
                age,
                message,
                candles
            FROM memorials
            WHERE approved = 1
            ORDER BY rowid DESC
            LIMIT 100
            """
        ).fetchall()

        return [dict(row) for row in rows]


@app.post("/api/memorials/{memorial_id}/candle")
def candle(
    memorial_id: str,
    authorization: str | None = Header(default=None),
):
    token = bearer_token(authorization)

    if not 32 <= len(token) <= 200:
        raise HTTPException(
            status_code=401,
            detail="A browser candle token is required.",
        )

    with db() as connection:
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            """
            SELECT id
            FROM memorials
            WHERE id = ? AND approved = 1
            """,
            (memorial_id,),
        ).fetchone()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Memorial not found.",
            )

        added = connection.execute(
            """
            INSERT OR IGNORE INTO candles (
                memorial_id,
                voter
            )
            VALUES (?, ?)
            """,
            (
                memorial_id,
                token_hash(token),
            ),
        ).rowcount

        if added:
            connection.execute(
                """
                UPDATE memorials
                SET candles = candles + 1
                WHERE id = ?
                """,
                (memorial_id,),
            )

    return {
        "added": bool(added),
    }
