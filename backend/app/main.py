from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .extensions import limiter
from .routers import (
    assets,
    auth,
    briefing,
    cash,
    dashboard,
    decision_log,
    discovery,
    funds,
    instruments,
    intelligence,
    liabilities,
    opportunities,
    prices,
    research,
    statements,
    symbols,
    transactions,
    watchlist,
    copilot,
    copilot_v2,
    investor_profile,
    financial_context,
)

from .services.scheduler import scheduler
from .utils.currency import ExchangeRateNotFoundError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    info = scheduler.get_schedule_info()
    if settings.BRIEFING_SCHEDULER_ENABLED:
        logger.info(
            "Starting application with scheduled briefings enabled [Timezone: %s | Local Target: %s | UTC: %s | Next Local: %s]",
            info["timezone"],
            info["local_target"],
            info["utc_target"],
            info["next_local_execution"],
        )
        scheduler.start()
    else:
        logger.info(
            "Application started with scheduled briefings disabled [Configured: %s (%s) / %s]",
            info["local_target"],
            info["timezone"],
            info["utc_target"],
        )
    try:
        yield
    finally:
        if scheduler.is_running:
            await scheduler.stop()


app = FastAPI(title="NetWorth API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(instruments.router, prefix="/api/instruments", tags=["instruments"])
app.include_router(intelligence.router, prefix="/api/instruments", tags=["intelligence"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
app.include_router(symbols.router, prefix="/api/symbols", tags=["symbols"])
app.include_router(funds.router, prefix="/api/funds", tags=["funds"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["transactions"])
app.include_router(cash.router, prefix="/api/cash", tags=["cash"])
app.include_router(
    liabilities.router, prefix="/api/liabilities", tags=["liabilities"]
)
app.include_router(statements.router, prefix="/api", tags=["statements"])
app.include_router(decision_log.router, prefix="/api/decisions", tags=["decisions"])
app.include_router(briefing.router, prefix="/api/briefing", tags=["briefing"])
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(opportunities.router, prefix="/api/opportunities", tags=["opportunities"])
app.include_router(discovery.router, prefix="/api/discovery", tags=["discovery"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(copilot.router, prefix="/api/copilot", tags=["copilot"])
app.include_router(copilot_v2.router)
app.include_router(investor_profile.router)
app.include_router(financial_context.router)


# ---------------------------------------------------------------------------
# Global exception handlers → consistent {"status":"error","message":"..."}
# ---------------------------------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Invalid request data",
            "details": jsonable_encoder(exc.errors(), custom_encoder={Exception: str}),
        },
    )


@app.exception_handler(ExchangeRateNotFoundError)
async def exchange_rate_exception_handler(
    _request: Request, exc: ExchangeRateNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=424,
        content={
            "status": "error",
            "message": "Required exchange rate is unavailable",
            "code": "exchange_rate_unavailable",
            "details": {"missing_rates": list(exc.missing_pairs)},
        },
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["health"])
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "success", "data": {"service": "networth-api", "version": "1.0.0"}}
