"""FastAPI application entry point for UCIF API transport layer"""
import logging
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from backend.config import settings
from . import dependencies
from .routers import health, framework, upload, analysis, executions

logger = logging.getLogger(__name__)

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        logger.info(f"Request {request_id} - {request.method} {request.url.path}")
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

def create_app() -> FastAPI:
    app = FastAPI(
        title="Universal Churn Intelligence Framework API",
        version=settings.API_VERSION,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    app.add_middleware(RequestIdMiddleware)

    # Register routers under /api/v1
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(framework.router, prefix="/api/v1")
    app.include_router(upload.router, prefix="/api/v1")
    app.include_router(analysis.router, prefix="/api/v1")
    app.include_router(executions.router, prefix="/api/v1")

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(), "body": exc.body},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc: Exception):
        logger.exception(f"Unhandled exception for request {getattr(request.state, 'request_id', 'unknown')}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app

app = create_app()
