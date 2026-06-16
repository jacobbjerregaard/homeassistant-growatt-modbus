"""Thin async client for the EMHASS REST API.

EMHASS (Energy Management for Home Assistant, https://github.com/davidusb-geek/emhass)
runs the actual optimisation. This integration only *triggers* an optimisation
and reads the result back from the sensors EMHASS publishes into Home Assistant.

The EMHASS ``/action/<name>`` endpoints return a short status string (e.g.
``"EMHASS >> Action dayahead-optim executed... \\n"``), not the optimisation
data, so this client is deliberately small: it POSTs the requested action with
optional runtime parameters and turns transport/HTTP failures into
``EmhassError``. Reading the optimised plan back is the optimizer's job (it
reads the published ``sensor.p_batt_forecast`` etc.), not this client's.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30

ACTION_DAYAHEAD = "dayahead-optim"
ACTION_NAIVE_MPC = "naive-mpc-optim"
ACTION_PUBLISH = "publish-data"


class EmhassError(Exception):
    """Raised when an EMHASS request cannot be completed."""


class EmhassClient:
    """Triggers EMHASS optimisations over its REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        token: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self) -> dict[str, str]:
        # aiohttp sets Content-Type: application/json automatically for ``json=``.
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def async_run_action(
        self, action: str, runtime_params: dict | None = None
    ) -> str:
        """POST one EMHASS action and return its status string.

        ``runtime_params`` is sent as the JSON body so callers can override
        forecasts or pass live values such as ``soc_init``.
        """
        url = f"{self._base_url}/action/{action}"
        try:
            async with self._session.post(
                url,
                json=runtime_params or {},
                headers=self._headers(),
                timeout=self._timeout,
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise EmhassError(
                        f"EMHASS action '{action}' returned HTTP {resp.status}: "
                        f"{text.strip()}"
                    )
                _LOGGER.debug("EMHASS action '%s' ok: %s", action, text.strip())
                return text
        except asyncio.TimeoutError as err:
            raise EmhassError(f"EMHASS action '{action}' timed out") from err
        except aiohttp.ClientError as err:
            raise EmhassError(f"EMHASS action '{action}' failed: {err}") from err

    async def async_dayahead_optim(self, runtime_params: dict | None = None) -> str:
        """Run the day-ahead (full-horizon LP) optimisation."""
        return await self.async_run_action(ACTION_DAYAHEAD, runtime_params)

    async def async_naive_mpc_optim(self, runtime_params: dict | None = None) -> str:
        """Run the naive model-predictive-control optimisation."""
        return await self.async_run_action(ACTION_NAIVE_MPC, runtime_params)

    async def async_publish_data(self, runtime_params: dict | None = None) -> str:
        """Publish the latest optimisation results to Home Assistant sensors."""
        return await self.async_run_action(ACTION_PUBLISH, runtime_params)

    async def async_test_connection(self) -> bool:
        """Best-effort reachability check used by the config flow.

        Any HTTP response (even an error status) means the server is up, so we
        only fail on transport-level errors.
        """
        try:
            async with self._session.get(
                self._base_url, timeout=self._timeout
            ) as resp:
                _LOGGER.debug("EMHASS reachable at %s (HTTP %s)", self._base_url, resp.status)
                return True
        except asyncio.TimeoutError as err:
            raise EmhassError("EMHASS connection timed out") from err
        except aiohttp.ClientError as err:
            raise EmhassError(f"Cannot reach EMHASS at {self._base_url}: {err}") from err
