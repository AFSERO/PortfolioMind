"""Configuration loader for the PortfolioMind bridge."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PortfolioMindBridgeConfig:
    """Settings governing connection and synchronization with PortfolioMind."""

    enabled: bool = False
    base_url: str = "http://localhost:8000"
    api_token: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    timeout: float = 15.0

    @classmethod
    def from_env(cls) -> "PortfolioMindBridgeConfig":
        """Load configuration safely from environment variables and .env files."""
        try:
            from dotenv import load_dotenv, find_dotenv
            dotenv_path = find_dotenv(usecwd=True)
            if dotenv_path:
                load_dotenv(dotenv_path)
            else:
                load_dotenv()
        except ImportError:
            pass

        enabled_val = os.getenv("PORTFOLIOMIND_SYNC_ENABLED", "").strip().lower()
        enabled = enabled_val in ("1", "true", "yes", "on")
        base_url = os.getenv("PORTFOLIOMIND_BASE_URL", "http://localhost:8000").rstrip("/")
        api_token = os.getenv("PORTFOLIOMIND_API_TOKEN") or None
        email = os.getenv("PORTFOLIOMIND_EMAIL") or None
        password = os.getenv("PORTFOLIOMIND_PASSWORD") or None
        timeout_str = os.getenv("PORTFOLIOMIND_TIMEOUT", "15.0")
        try:
            timeout = float(timeout_str)
        except ValueError:
            timeout = 15.0

        return cls(
            enabled=enabled,
            base_url=base_url,
            api_token=api_token,
            email=email,
            password=password,
            timeout=timeout,
        )
