"""HTTP client for communicating with PortfolioMind API."""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import httpx

from investment_intelligence.portfoliomind.config import PortfolioMindBridgeConfig
from investment_intelligence.portfoliomind.exceptions import (
    PortfolioMindAuthenticationError,
    PortfolioMindSyncError,
)
from investment_intelligence.portfoliomind.resolver import SafeInstrumentResolver


class PortfolioMindClient:
    """Client for PortfolioMind backend APIs."""

    def __init__(
        self,
        config: Optional[PortfolioMindBridgeConfig] = None,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self.config = config or PortfolioMindBridgeConfig.from_env()
        self.transport = transport
        self._token: Optional[str] = self.config.api_token

    def _get_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            transport=self.transport,
        )

    def authenticate(self) -> str:
        """Ensure an access token is available, logging in via API if credentials configured."""
        if self._token:
            return self._token

        if not self.config.email or not self.config.password:
            raise PortfolioMindAuthenticationError(
                "Neither PORTFOLIOMIND_API_TOKEN nor (PORTFOLIOMIND_EMAIL + PORTFOLIOMIND_PASSWORD) configured"
            )

        with self._get_client() as client:
            resp = client.post(
                "/api/auth/login",
                json={"email": self.config.email, "password": self.config.password},
            )
            if resp.status_code != 200:
                raise PortfolioMindAuthenticationError(
                    f"PortfolioMind login failed with status {resp.status_code}: {resp.text}"
                )
            data = resp.json().get("data", {})
            self._token = data.get("access_token")
            if not self._token:
                raise PortfolioMindAuthenticationError("No access_token returned by login endpoint")
            return self._token

    def _auth_headers(self) -> dict[str, str]:
        token = self.authenticate()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def resolve_instrument(
        self,
        symbol: str,
        *,
        asset_type: Optional[str] = None,
        venue: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> UUID:
        """Query PortfolioMind instruments and resolve safely to a single Instrument UUID."""
        with self._get_client() as client:
            target_type = SafeInstrumentResolver.map_asset_type(asset_type)
            params: dict[str, Any] = {"q": symbol, "limit": 50}
            if target_type:
                params["asset_type"] = target_type

            resp = client.get("/api/instruments", params=params, headers=self._auth_headers())
            if resp.status_code != 200:
                raise PortfolioMindSyncError(
                    f"Failed to query instruments: HTTP {resp.status_code} - {resp.text}"
                )

            candidates = resp.json().get("data", [])
            return SafeInstrumentResolver.resolve_from_candidates(
                candidates,
                symbol=symbol,
                asset_type=asset_type,
                venue=venue,
                currency=currency,
            )

    def post_review(
        self,
        instrument_id: UUID,
        *,
        protocol: str,
        status: str = "COMPLETED",
        run_type: Optional[str] = None,
        machine_record: Optional[dict[str, Any]] = None,
        human_brief: Optional[str] = None,
        confidence: Optional[str] = None,
        research_path: Optional[str] = None,
        source_run_id: Optional[str] = None,
        auto_apply_state: bool = True,
        is_synthetic: bool = False,
    ) -> dict[str, Any]:
        """Post an intelligence review to PortfolioMind."""
        payload = {
            "protocol": protocol,
            "status": status,
            "run_type": run_type,
            "machine_record": machine_record,
            "human_brief": human_brief,
            "confidence": confidence,
            "research_path": research_path,
            "source_run_id": source_run_id,
            "auto_apply_state": auto_apply_state,
            "is_synthetic": is_synthetic,
        }
        with self._get_client() as client:
            resp = client.post(
                f"/api/instruments/{instrument_id}/reviews",
                json=payload,
                headers=self._auth_headers(),
            )
            if resp.status_code not in (200, 201):
                raise PortfolioMindSyncError(
                    f"Failed to post review: HTTP {resp.status_code} - {resp.text}"
                )
            return resp.json().get("data", {})

    def put_technical_plan(
        self,
        instrument_id: UUID,
        plan_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Put or update an active technical plan on PortfolioMind."""
        with self._get_client() as client:
            resp = client.put(
                f"/api/instruments/{instrument_id}/technical-plan",
                json=plan_data,
                headers=self._auth_headers(),
            )
            if resp.status_code != 200:
                raise PortfolioMindSyncError(
                    f"Failed to put technical plan: HTTP {resp.status_code} - {resp.text}"
                )
            return resp.json().get("data", {})

    def get_intelligence_state(self, instrument_id: UUID) -> Optional[dict[str, Any]]:
        """Retrieve current intelligence state for an instrument."""
        with self._get_client() as client:
            resp = client.get(
                f"/api/instruments/{instrument_id}/intelligence",
                headers=self._auth_headers(),
            )
            if resp.status_code != 200:
                raise PortfolioMindSyncError(
                    f"Failed to get intelligence state: HTTP {resp.status_code} - {resp.text}"
                )
            return resp.json().get("data")


class AsyncPortfolioMindClient:
    """Asynchronous client for PortfolioMind backend APIs."""

    def __init__(
        self,
        config: Optional[PortfolioMindBridgeConfig] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.config = config or PortfolioMindBridgeConfig.from_env()
        self.transport = transport
        self._token: Optional[str] = self.config.api_token

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            transport=self.transport,
        )

    async def authenticate(self) -> str:
        if self._token:
            return self._token

        if not self.config.email or not self.config.password:
            raise PortfolioMindAuthenticationError(
                "Neither PORTFOLIOMIND_API_TOKEN nor (PORTFOLIOMIND_EMAIL + PORTFOLIOMIND_PASSWORD) configured"
            )

        async with self._get_client() as client:
            resp = await client.post(
                "/api/auth/login",
                json={"email": self.config.email, "password": self.config.password},
            )
            if resp.status_code != 200:
                raise PortfolioMindAuthenticationError(
                    f"PortfolioMind login failed with status {resp.status_code}: {resp.text}"
                )
            data = resp.json().get("data", {})
            self._token = data.get("access_token")
            if not self._token:
                raise PortfolioMindAuthenticationError("No access_token returned by login endpoint")
            return self._token

    async def _auth_headers(self) -> dict[str, str]:
        token = await self.authenticate()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def resolve_instrument(
        self,
        symbol: str,
        *,
        asset_type: Optional[str] = None,
        venue: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> UUID:
        async with self._get_client() as client:
            target_type = SafeInstrumentResolver.map_asset_type(asset_type)
            params: dict[str, Any] = {"q": symbol, "limit": 50}
            if target_type:
                params["asset_type"] = target_type

            headers = await self._auth_headers()
            resp = await client.get("/api/instruments", params=params, headers=headers)
            if resp.status_code != 200:
                raise PortfolioMindSyncError(
                    f"Failed to query instruments: HTTP {resp.status_code} - {resp.text}"
                )

            candidates = resp.json().get("data", [])
            return SafeInstrumentResolver.resolve_from_candidates(
                candidates,
                symbol=symbol,
                asset_type=asset_type,
                venue=venue,
                currency=currency,
            )

    async def post_review(
        self,
        instrument_id: UUID,
        *,
        protocol: str,
        status: str = "COMPLETED",
        run_type: Optional[str] = None,
        machine_record: Optional[dict[str, Any]] = None,
        human_brief: Optional[str] = None,
        confidence: Optional[str] = None,
        research_path: Optional[str] = None,
        source_run_id: Optional[str] = None,
        auto_apply_state: bool = True,
        is_synthetic: bool = False,
    ) -> dict[str, Any]:
        payload = {
            "protocol": protocol,
            "status": status,
            "run_type": run_type,
            "machine_record": machine_record,
            "human_brief": human_brief,
            "confidence": confidence,
            "research_path": research_path,
            "source_run_id": source_run_id,
            "auto_apply_state": auto_apply_state,
            "is_synthetic": is_synthetic,
        }
        async with self._get_client() as client:
            headers = await self._auth_headers()
            resp = await client.post(
                f"/api/instruments/{instrument_id}/reviews",
                json=payload,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                raise PortfolioMindSyncError(
                    f"Failed to post review: HTTP {resp.status_code} - {resp.text}"
                )
            return resp.json().get("data", {})

    async def put_technical_plan(
        self,
        instrument_id: UUID,
        plan_data: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._get_client() as client:
            headers = await self._auth_headers()
            resp = await client.put(
                f"/api/instruments/{instrument_id}/technical-plan",
                json=plan_data,
                headers=headers,
            )
            if resp.status_code != 200:
                raise PortfolioMindSyncError(
                    f"Failed to put technical plan: HTTP {resp.status_code} - {resp.text}"
                )
            return resp.json().get("data", {})

    async def get_intelligence_state(self, instrument_id: UUID) -> Optional[dict[str, Any]]:
        async with self._get_client() as client:
            headers = await self._auth_headers()
            resp = await client.get(
                f"/api/instruments/{instrument_id}/intelligence",
                headers=headers,
            )
            if resp.status_code != 200:
                raise PortfolioMindSyncError(
                    f"Failed to get intelligence state: HTTP {resp.status_code} - {resp.text}"
                )
            return resp.json().get("data")
