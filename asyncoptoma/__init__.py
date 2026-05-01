from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

__all__ = ["Optoma", "OptomaError", "OptomaAuthError"]

_LOGGER = logging.getLogger(__name__)

_CONTROL_PATH = "/tgi/control.tgi"
_LOGIN_PATH = "/tgi/login.tgi"

_DROPDOWNS: tuple[str, ...] = (
    "source",
    "Degamma",
    "Degamma2",
    "colortmp",
    "dismode0",
    "dismode1",
    "colorsp0",
    "colorsp1",
    "aspect0",
    "aspect1",
    "screen",
    "projection",
    "background",
    "wall",
    "logo",
    "pwmode",
    "lampmd",
)

_TOGGLES: tuple[str, ...] = (
    "avmute",
    "freeze",
    "infohide",
    "altitude",
    "keypad",
    "dismdlocked",
    "directpwon",
    "alwayson",
)

_INPUTS: tuple[str, ...] = (
    "bright",
    "contrast",
    "Sharp",
    "Phase",
    "brill",
    "zoom",
    "hpos",
    "vpos",
    "autopw",
    "sleep",
    "projid",
)

_TOGGLE_COMMAND_LABELS: dict[str, str] = {
    "avmute": "AV Mute",
    "freeze": "Freeze",
    "infohide": "Information Hide",
    "altitude": "High Altitude",
    "keypad": "Keypad Lock",
    "dismdlocked": "Display Mode Lock",
    "directpwon": "Direct Power On",
    "alwayson": "Always On",
}


class OptomaError(Exception):
    """Base class for asyncoptoma errors."""


class OptomaAuthError(OptomaError):
    """Raised when authentication with the projector fails."""


class Optoma:
    def __init__(
        self,
        base_url: str,
        username: str = "admin",
        password: str = "admin",
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._owns_client = client is None
        self.http = client if client is not None else httpx.AsyncClient(timeout=timeout)
        self.status: dict[str, Any] = {
            **{f"available_{name}": {} for name in _DROPDOWNS},
            **{f"active_{name}": None for name in _DROPDOWNS},
            **{name: None for name in _TOGGLES},
            **{name: None for name in _INPUTS},
            "power": None,
        }

    async def __aenter__(self) -> Optoma:
        await self.login()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self.http.aclose()

    async def _make_request(
        self, method: str, path: str, data: dict[str, Any] | None = None
    ) -> httpx.Response:
        try:
            response = await self.http.request(
                method.upper(), f"{self.base_url}{path}", data=data
            )
        except httpx.HTTPError as exc:
            raise OptomaError(f"HTTP request to {path} failed: {exc}") from exc
        if response.status_code >= 400:
            raise OptomaError(
                f"HTTP {response.status_code} from {path}: {response.text[:200]}"
            )
        return response

    async def login(self) -> None:
        response = await self._make_request("GET", "/login.htm")
        soup = BeautifulSoup(response.text, "html.parser")
        challenge_element = soup.find("input", {"name": "Challenge"})
        if challenge_element is None or not isinstance(challenge_element, Tag):
            raise OptomaAuthError("Login challenge not found in response")

        challenge_value = challenge_element.get("value")
        if not isinstance(challenge_value, str):
            raise OptomaAuthError("Login challenge value missing or malformed")

        login_hash = hashlib.md5(
            f"{self.username}{self.password}{challenge_value}".encode(),
            usedforsecurity=False,
        ).hexdigest()
        data = {
            "user": 0,
            "Username": self.username,
            "Password": "",
            "Challenge": "",
            "Response": login_hash,
        }

        await self._make_request("POST", _LOGIN_PATH, data=data)
        await self.update_status()

    @staticmethod
    def _parse_drop_down_options(
        select_element: Tag,
    ) -> tuple[list[dict[str, Any]], str | None]:
        options: list[dict[str, Any]] = []
        selected: str | None = None
        for option_element in select_element.find_all("option"):
            label = (
                option_element.get_text().replace("\n", " ").replace(".", "").strip()
            )
            try:
                option_id = int(option_element["value"])
            except (KeyError, ValueError):
                continue
            options.append({"id": option_id, "label": label})
            if option_element.has_attr("selected"):
                selected = label
        options.sort(key=lambda i: i["id"])
        return options, selected

    async def update_status(self) -> None:
        response = await self._make_request("GET", "/control.htm")
        soup = BeautifulSoup(response.text, "html.parser")

        dropdowns = set(_DROPDOWNS)
        for select in soup.find_all("select"):
            key = select.get("id")
            if key in dropdowns:
                options, active = self._parse_drop_down_options(select)
                self.status[f"available_{key}"] = {o["label"]: o["id"] for o in options}
                self.status[f"active_{key}"] = active

        toggles = set(_TOGGLES)
        for btn in soup.find_all("td"):
            key = btn.get("id", "")
            if key.endswith("_td"):
                name = key[:-3]
                if name in toggles:
                    self.status[name] = btn.get_text().strip() in ("On", "Yes")

        inputs = set(_INPUTS)
        for inp in soup.find_all("input"):
            key = inp.get("id")
            if key in inputs:
                try:
                    self.status[key] = int(inp["value"])
                except (KeyError, ValueError):
                    self.status[key] = None

        power = soup.find("input", {"id": "pwr"})
        if power is not None and power.has_attr("value"):
            try:
                self.status["power"] = int(power["value"]) == 1
            except ValueError:
                self.status["power"] = None

    async def _set_choice(self, field: str, value: str) -> None:
        if self.status.get(f"active_{field}") == value:
            return
        available = self.status.get(f"available_{field}") or {}
        if value not in available:
            _LOGGER.warning("Value %r not available for %s", value, field)
            return
        await self._make_request("POST", _CONTROL_PATH, {field: available[value]})
        self.status[f"active_{field}"] = value

    async def _set_value(self, field: str, value: int) -> None:
        await self._make_request("POST", _CONTROL_PATH, {field: value})
        self.status[field] = value

    async def _toggle(self, field: str, value: bool) -> None:
        if self.status.get(field) is None:
            await self.update_status()
        if self.status.get(field) == value:
            return
        await self._make_request(
            "POST", _CONTROL_PATH, {field: _TOGGLE_COMMAND_LABELS[field]}
        )
        self.status[field] = value

    # -- Sources --
    def get_available_sources(self) -> dict[str, int]:
        return self.status["available_source"]

    def get_active_source(self) -> str | None:
        return self.status["active_source"]

    async def set_active_source(self, value: str) -> None:
        await self._set_choice("source", value)

    # -- Display mode 0 --
    def get_available_dismodes_0(self) -> dict[str, int]:
        return self.status["available_dismode0"]

    def get_active_dismode_0(self) -> str | None:
        return self.status["active_dismode0"]

    async def set_active_dismode_0(self, value: str) -> None:
        await self._set_choice("dismode0", value)

    # -- Display mode 1 --
    def get_available_dismodes_1(self) -> dict[str, int]:
        return self.status["available_dismode1"]

    def get_active_dismode_1(self) -> str | None:
        return self.status["active_dismode1"]

    async def set_active_dismode_1(self, value: str) -> None:
        await self._set_choice("dismode1", value)

    # -- Color space 0 --
    def get_available_colorsps_0(self) -> dict[str, int]:
        return self.status["available_colorsp0"]

    def get_active_colorsp_0(self) -> str | None:
        return self.status["active_colorsp0"]

    async def set_active_colorsp_0(self, value: str) -> None:
        await self._set_choice("colorsp0", value)

    # -- Color space 1 --
    def get_available_colorsps_1(self) -> dict[str, int]:
        return self.status["available_colorsp1"]

    def get_active_colorsp_1(self) -> str | None:
        return self.status["active_colorsp1"]

    async def set_active_colorsp_1(self, value: str) -> None:
        await self._set_choice("colorsp1", value)

    # -- Gamma --
    def get_available_gammas(self) -> dict[str, int]:
        return self.status["available_Degamma"]

    def get_active_gamma(self) -> str | None:
        return self.status["active_Degamma"]

    async def set_active_gamma(self, value: str) -> None:
        await self._set_choice("Degamma", value)

    # -- Brightness / lamp mode --
    def get_available_brightness_modes(self) -> dict[str, int]:
        return self.status["available_lampmd"]

    def get_active_brightness_mode(self) -> str | None:
        return self.status["active_lampmd"]

    async def set_active_brightness_mode(self, value: str) -> None:
        await self._set_choice("lampmd", value)

    # -- Color temperature --
    def get_available_color_temperature(self) -> dict[str, int]:
        return self.status["available_colortmp"]

    def get_active_color_temperature(self) -> str | None:
        return self.status["active_colortmp"]

    async def set_active_color_temperature(self, value: str) -> None:
        await self._set_choice("colortmp", value)

    # -- Logo --
    def get_available_logo(self) -> dict[str, int]:
        return self.status["available_logo"]

    def get_active_logo(self) -> str | None:
        return self.status["active_logo"]

    async def set_active_logo(self, value: str) -> None:
        await self._set_choice("logo", value)

    # -- Power mode --
    def get_available_power_modes(self) -> dict[str, int]:
        return self.status["available_pwmode"]

    def get_active_power_mode(self) -> str | None:
        return self.status["active_pwmode"]

    async def set_active_power_mode(self, value: str) -> None:
        await self._set_choice("pwmode", value)

    # -- Toggles --
    def get_info_hide(self) -> bool | None:
        return self.status["infohide"]

    async def set_info_hide(self, value: bool) -> None:
        await self._toggle("infohide", value)

    def get_always_on(self) -> bool | None:
        return self.status["alwayson"]

    async def set_always_on(self, value: bool) -> None:
        await self._toggle("alwayson", value)

    def get_freeze(self) -> bool | None:
        return self.status["freeze"]

    async def set_freeze(self, value: bool) -> None:
        await self._toggle("freeze", value)

    def get_av_mute(self) -> bool | None:
        return self.status["avmute"]

    async def set_av_mute(self, value: bool) -> None:
        await self._toggle("avmute", value)

    def get_high_altitude(self) -> bool | None:
        return self.status["altitude"]

    async def set_high_altitude(self, value: bool) -> None:
        await self._toggle("altitude", value)

    def get_keypad_lock(self) -> bool | None:
        return self.status["keypad"]

    async def set_keypad_lock(self, value: bool) -> None:
        await self._toggle("keypad", value)

    def get_display_mode_lock(self) -> bool | None:
        return self.status["dismdlocked"]

    async def set_display_mode_lock(self, value: bool) -> None:
        await self._toggle("dismdlocked", value)

    def get_direct_power_on(self) -> bool | None:
        return self.status["directpwon"]

    async def set_direct_power_on(self, value: bool) -> None:
        await self._toggle("directpwon", value)

    # -- Numeric values --
    def get_zoom(self) -> int | None:
        return self.status["zoom"]

    async def set_zoom(self, value: int) -> None:
        await self._set_value("zoom", value)

    def get_horizontal_shift(self) -> int | None:
        return self.status["hpos"]

    async def set_horizontal_shift(self, value: int) -> None:
        await self._set_value("hpos", value)

    def get_vertical_shift(self) -> int | None:
        return self.status["vpos"]

    async def set_vertical_shift(self, value: int) -> None:
        await self._set_value("vpos", value)

    def get_auto_power_off(self) -> int | None:
        return self.status["autopw"]

    async def set_auto_power_off(self, value: int) -> None:
        await self._set_value("autopw", value)

    def get_sleep_timer(self) -> int | None:
        return self.status["sleep"]

    async def set_sleep_timer(self, value: int) -> None:
        await self._set_value("sleep", value)

    def get_projector_id(self) -> int | None:
        return self.status["projid"]

    async def set_projector_id(self, value: int) -> None:
        await self._set_value("projid", value)

    def get_brightness(self) -> int | None:
        return self.status["bright"]

    async def set_brightness(self, value: int) -> None:
        await self._set_value("bright", value)

    def get_contrast(self) -> int | None:
        return self.status["contrast"]

    async def set_contrast(self, value: int) -> None:
        await self._set_value("contrast", value)

    def get_sharpness(self) -> int | None:
        return self.status["Sharp"]

    async def set_sharpness(self, value: int) -> None:
        await self._set_value("Sharp", value)

    def get_phase(self) -> int | None:
        return self.status["Phase"]

    async def set_phase(self, value: int) -> None:
        await self._set_value("Phase", value)

    def get_brilliant_color(self) -> int | None:
        return self.status["brill"]

    async def set_brilliant_color(self, value: int) -> None:
        await self._set_value("brill", value)

    # -- Commands --
    async def resync(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"resync": "Resync"})

    async def reset(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"reset": "Reset"})

    def get_power(self) -> bool | None:
        return self.status["power"]

    async def turn_on(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"btn_powon": "Power On"})
        self.status["power"] = True

    async def turn_off(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"btn_powoff": "Power Off"})
        self.status["power"] = False
