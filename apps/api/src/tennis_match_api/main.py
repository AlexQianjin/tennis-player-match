import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from tennis_match_api.config import get_settings
from tennis_match_api.db import dispose_engine
from tennis_match_api.errors import BizError
from tennis_match_api.logging_setup import configure_logging
from tennis_match_api.routers.auth import router as auth_router
from tennis_match_api.routers.court import router as court_router
from tennis_match_api.routers.health import router as health_router
from tennis_match_api.routers.user import router as user_router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log.info(
        "startup",
        extra={
            "event": "startup",
            "auth_mode": settings.auth_mode,
            "message": "confirm public network access is disabled before trusting X-WX-OPENID",
        },
    )
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="tennis-match-api", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(court_router)

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        log.info(
            "request",
            extra={
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response

    @app.exception_handler(BizError)
    async def biz_error(_request: Request, exc: BizError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message, "data": exc.data},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "code": 400,
                "message": "参数错误",
                "data": {"errors": _jsonable(exc.errors())},
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = 400 if exc.status_code == 422 else exc.status_code
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": str(exc.detail), "data": None},
        )

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled", extra={"event": "unhandled"})
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": "服务器错误", "data": None},
        )

    return app


def _jsonable(value: object) -> object:
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "tennis_match_api.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,
    )
