from __future__ import annotations

import hashlib

import httpx
import pytest
import respx

from asyncoptoma import Optoma, OptomaAuthError, OptomaError

BASE_URL = "http://projector.local"

LOGIN_HTML = """
<html><body>
<form>
  <input name="Challenge" value="abc123" />
</form>
</body></html>
"""

CONTROL_HTML = """
<html><body>
<select id="source">
  <option value="1">HDMI 1</option>
  <option value="2" selected>HDMI 2/MHL</option>
  <option value="3">VGA</option>
</select>
<select id="lampmd">
  <option value="0" selected>Bright</option>
  <option value="1">Power 50%</option>
</select>
<td id="avmute_td">Off</td>
<td id="freeze_td">On</td>
<input id="bright" value="50" />
<input id="zoom" value="-3" />
<input id="pwr" value="1" />
</body></html>
"""


@pytest.fixture
def optoma() -> Optoma:
    return Optoma(BASE_URL, username="admin", password="admin")


@respx.mock
async def test_login_success(optoma: Optoma) -> None:
    respx.get(f"{BASE_URL}/login.htm").mock(
        return_value=httpx.Response(200, text=LOGIN_HTML)
    )
    login_route = respx.post(f"{BASE_URL}/tgi/login.tgi").mock(
        return_value=httpx.Response(200, text="ok")
    )
    respx.get(f"{BASE_URL}/control.htm").mock(
        return_value=httpx.Response(200, text=CONTROL_HTML)
    )

    await optoma.login()

    assert login_route.called
    sent = dict(httpx.QueryParams(login_route.calls.last.request.content.decode()))
    expected_hash = hashlib.md5(b"adminadminabc123", usedforsecurity=False).hexdigest()
    assert sent["Response"] == expected_hash
    assert sent["Username"] == "admin"
    assert optoma.get_active_source() == "HDMI 2/MHL"
    assert optoma.get_brightness() == 50
    assert optoma.get_power() is True

    await optoma.close()


@respx.mock
async def test_login_missing_challenge(optoma: Optoma) -> None:
    respx.get(f"{BASE_URL}/login.htm").mock(
        return_value=httpx.Response(200, text="<html></html>")
    )

    with pytest.raises(OptomaAuthError):
        await optoma.login()

    await optoma.close()


@respx.mock
async def test_http_error_raises_optoma_error(optoma: Optoma) -> None:
    respx.get(f"{BASE_URL}/login.htm").mock(
        return_value=httpx.Response(500, text="boom")
    )

    with pytest.raises(OptomaError):
        await optoma.login()

    await optoma.close()


@respx.mock
async def test_set_active_source_skips_when_already_active(optoma: Optoma) -> None:
    respx.get(f"{BASE_URL}/login.htm").mock(
        return_value=httpx.Response(200, text=LOGIN_HTML)
    )
    respx.post(f"{BASE_URL}/tgi/login.tgi").mock(
        return_value=httpx.Response(200, text="ok")
    )
    respx.get(f"{BASE_URL}/control.htm").mock(
        return_value=httpx.Response(200, text=CONTROL_HTML)
    )
    control_route = respx.post(f"{BASE_URL}/tgi/control.tgi").mock(
        return_value=httpx.Response(200, text="ok")
    )

    await optoma.login()
    await optoma.set_active_source("HDMI 2/MHL")
    assert not control_route.called

    await optoma.set_active_source("HDMI 1")
    assert control_route.called

    await optoma.close()


@respx.mock
async def test_async_context_manager_logs_in() -> None:
    respx.get(f"{BASE_URL}/login.htm").mock(
        return_value=httpx.Response(200, text=LOGIN_HTML)
    )
    respx.post(f"{BASE_URL}/tgi/login.tgi").mock(
        return_value=httpx.Response(200, text="ok")
    )
    respx.get(f"{BASE_URL}/control.htm").mock(
        return_value=httpx.Response(200, text=CONTROL_HTML)
    )

    async with Optoma(BASE_URL, username="admin", password="admin") as projector:
        assert projector.get_power() is True
        assert "HDMI 1" in projector.get_available_sources()


@respx.mock
async def test_turn_on_off_updates_state(optoma: Optoma) -> None:
    respx.post(f"{BASE_URL}/tgi/control.tgi").mock(
        return_value=httpx.Response(200, text="ok")
    )

    await optoma.turn_on()
    assert optoma.get_power() is True

    await optoma.turn_off()
    assert optoma.get_power() is False

    await optoma.close()


@respx.mock
async def test_toggle_fetches_status_when_unknown(optoma: Optoma) -> None:
    respx.get(f"{BASE_URL}/control.htm").mock(
        return_value=httpx.Response(200, text=CONTROL_HTML)
    )
    control_route = respx.post(f"{BASE_URL}/tgi/control.tgi").mock(
        return_value=httpx.Response(200, text="ok")
    )

    # avmute is "Off" (False) in CONTROL_HTML, so requesting True must send the toggle.
    await optoma.set_av_mute(True)
    assert control_route.called
    assert optoma.get_av_mute() is True

    await optoma.close()
