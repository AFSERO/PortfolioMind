"""Optional live TEFAS availability probe, separate from deterministic pytest.

Run manually: python scripts/check_tefas_live.py. External unavailable or invalid
quotes cause a nonzero exit; they are never turned into fabricated prices.
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.providers.tefas import TefasFundProvider


async def main():
    provider = TefasFundProvider()
    available = True
    for code in ("KCV", "THF"):
        try:
            metadata = await provider.get_fund_info(code)
            print(json.dumps({"fund":code, "status":"available", "source_date":str(metadata.price_date)}))
        except (ValueError, RuntimeError):
            available = False
            print(json.dumps({"fund":code, "status":"unavailable_or_invalid_quote"}))
    return 0 if available else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
