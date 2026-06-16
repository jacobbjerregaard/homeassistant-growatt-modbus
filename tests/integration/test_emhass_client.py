"""Tests for the thin EMHASS REST client.

Only the HTTP wire is mocked (via ``aioclient_mock``); the request building,
JSON body and error handling are real.
"""
import aiohttp
import pytest

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.growatt_modbus.emhass_client import (
    EmhassClient,
    EmhassError,
)

BASE = "http://emhass.local:5000"


async def test_dayahead_optim_posts_action(hass, aioclient_mock):
    aioclient_mock.post(
        f"{BASE}/action/dayahead-optim",
        text="EMHASS >> Action dayahead-optim executed... \n",
    )
    client = EmhassClient(async_get_clientsession(hass), BASE)

    result = await client.async_dayahead_optim()

    assert "executed" in result
    assert len(aioclient_mock.mock_calls) == 1
    method, url, _data, _headers = aioclient_mock.mock_calls[0]
    assert method == "POST"
    assert str(url) == f"{BASE}/action/dayahead-optim"


async def test_trailing_slash_in_base_url_is_normalised(hass, aioclient_mock):
    aioclient_mock.post(f"{BASE}/action/publish-data", text="ok")
    client = EmhassClient(async_get_clientsession(hass), f"{BASE}/")

    await client.async_publish_data()

    _method, url, _data, _headers = aioclient_mock.mock_calls[0]
    assert str(url) == f"{BASE}/action/publish-data"


async def test_runtime_params_sent_as_json_body(hass, aioclient_mock):
    aioclient_mock.post(f"{BASE}/action/naive-mpc-optim", text="ok")
    client = EmhassClient(async_get_clientsession(hass), BASE)

    await client.async_naive_mpc_optim({"soc_init": 0.42})

    _method, _url, data, _headers = aioclient_mock.mock_calls[0]
    assert data == {"soc_init": 0.42}


async def test_no_params_sends_empty_object(hass, aioclient_mock):
    aioclient_mock.post(f"{BASE}/action/dayahead-optim", text="ok")
    client = EmhassClient(async_get_clientsession(hass), BASE)

    await client.async_dayahead_optim()

    _method, _url, data, _headers = aioclient_mock.mock_calls[0]
    assert data == {}


async def test_token_sets_authorization_header(hass, aioclient_mock):
    aioclient_mock.post(f"{BASE}/action/dayahead-optim", text="ok")
    client = EmhassClient(async_get_clientsession(hass), BASE, token="s3cret")

    await client.async_dayahead_optim()

    _method, _url, _data, headers = aioclient_mock.mock_calls[0]
    assert headers["Authorization"] == "Bearer s3cret"


async def test_non_200_raises_emhass_error(hass, aioclient_mock):
    aioclient_mock.post(f"{BASE}/action/publish-data", status=500, text="boom")
    client = EmhassClient(async_get_clientsession(hass), BASE)

    with pytest.raises(EmhassError, match="HTTP 500"):
        await client.async_publish_data()


async def test_transport_error_raises_emhass_error(hass, aioclient_mock):
    aioclient_mock.post(
        f"{BASE}/action/dayahead-optim", exc=aiohttp.ClientError("nope")
    )
    client = EmhassClient(async_get_clientsession(hass), BASE)

    with pytest.raises(EmhassError, match="failed"):
        await client.async_dayahead_optim()


async def test_connection_check_ok(hass, aioclient_mock):
    aioclient_mock.get(BASE, text="<html>EMHASS</html>")
    client = EmhassClient(async_get_clientsession(hass), BASE)

    assert await client.async_test_connection() is True


async def test_connection_check_raises_when_unreachable(hass, aioclient_mock):
    aioclient_mock.get(BASE, exc=aiohttp.ClientError("refused"))
    client = EmhassClient(async_get_clientsession(hass), BASE)

    with pytest.raises(EmhassError, match="Cannot reach EMHASS"):
        await client.async_test_connection()
