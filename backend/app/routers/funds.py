"""Router for Turkish investment funds (TEFAS)."""

from fastapi import APIRouter, HTTPException, Query

from app.providers import get_fund_provider
from app.providers.tefas import InvalidFundQuoteError

router = APIRouter()


@router.get("/info/{fund_code}")
async def get_fund_info(fund_code: str) -> dict:
    """Return metadata and latest unit price for a TEFAS fund code."""
    provider = get_fund_provider()
    try:
        meta = await provider.get_fund_info(fund_code)
    except InvalidFundQuoteError:
        raise HTTPException(status_code=502, detail="TEFAS returned no usable fund quote") from None
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"TEFAS service error: {exc}"
        ) from None

    return {
        "status": "success",
        "data": {
            "fund_code": meta.fund_code,
            "fund_name": meta.fund_name,
            "price": float(meta.price),
            "currency": meta.currency,
            "price_date": meta.price_date.isoformat() if meta.price_date else None,
            "provider": meta.provider,
        },
    }


@router.get("/search")
async def search_funds(
    q: str = Query("", description="Search query (fund code or name substring)"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """Search TEFAS funds by code or title substring."""
    provider = get_fund_provider()
    try:
        results = await provider.search_funds(q, limit)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"TEFAS search error: {exc}"
        ) from None

    return {"status": "success", "data": results}


@router.get("/history/{fund_code}")
async def get_fund_history(
    fund_code: str,
    days: int = Query(30, ge=1, le=30, description="Lookback days (max 30)"),
) -> dict:
    """Return chronological historical prices for a TEFAS fund."""
    provider = get_fund_provider()
    try:
        history = await provider.get_fund_history(fund_code, days=days)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"TEFAS history error: {exc}"
        ) from None

    return {
        "status": "success",
        "data": [
            {
                "date": pt["date"],
                "price": float(pt["price"]),
                "currency": pt["currency"],
            }
            for pt in history
        ],
    }
