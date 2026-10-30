import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.openapi.utils import get_openapi
from src.audit import AuditEvent
from src.database import SessionLocal
from src.utils.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.utils.file_handler import ensure_upload_directory

from src.authentication.routers import router as auth_router
from src.roles.routers import router as roles_router
from src.documentation.routers import router as document_router

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_upload_directory()
    yield


app = FastAPI(
    title="Document Management & Secure File Sharing System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


def _persist_audit_event(
    actor_id: int | None,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    client_ip: str | None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AuditEvent(
                actor_id=actor_id,
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                client_ip=client_ip,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist request audit event", extra={"request_id": request_id})
    finally:
        db.close()


@app.middleware("http")
async def request_logging_and_audit(request: Request, call_next):
    request_id = uuid4().hex
    request.state.request_id = request_id
    started_at = time.perf_counter()
    client_ip = request.client.host if request.client else None

    try:
        response = await call_next(request)
    except Exception as exc:
        response = await unhandled_exception_handler(request, exc)

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "HTTP request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        },
    )

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        await run_in_threadpool(
            _persist_audit_event,
            getattr(request.state, "actor_user_id", None),
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            client_ip,
        )

    return response

app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(document_router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
    )
    upload_operation = openapi_schema["paths"]["/documents/upload"]["post"]
    request_schema = upload_operation["requestBody"]["content"]["multipart/form-data"]["schema"]
    schema_name = request_schema["$ref"].rsplit("/", 1)[-1]
    file_items = openapi_schema["components"]["schemas"][schema_name]["properties"]["files"]["items"]
    file_items["format"] = "binary"

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

@app.get("/")
def home():
    return {"message": "Document Management & Secure File Sharing System is running"}