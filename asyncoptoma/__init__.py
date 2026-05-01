from __future__ import annotations

import hashlib
import logging
from typing import Any, Awaitable, Callable

import httpx
from bs4 import BeautifulSoup, Tag

__all__ = ["Optoma", "OptomaError", "OptomaAuthError"]

_LOGGER = logging.getLogger(__name__)

_CONTROL_PATH = "/tgi/control.tgi"
_LOGIN_PATH = "/tgi/login.tgi"

# Every dropdown the projector exposes, including those without convenience methods.
_ALL_DROPDOWNS: tuple[str, ...] = (
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

# (raw_field, available_method_suffix, active_method_suffix)
_DROPDOWN_METHODS: tuple[tuple[str, str, str], ...] = (
    ("source", "sources", "source"),
    ("dismode0", "dismodes_0", "dismode_0"),
    ("dismode1", "dismodes_1", "dismode_1"),
    ("colorsp0", "colorsps_0", "colorsp_0"),
    ("colorsp1", "colorsps_1", "colorsp_1"),
    ("Degamma", "gammas", "gamma"),
    ("lampmd", "brightness_modes", "brightness_mode"),
    ("colortmp", "color_temperature", "color_temperature"),
    ("logo", "logo", "logo"),
    ("pwmode", "power_modes", "power_mode"),
)

# (raw_field, public_name, projector_command_label)
_TOGGLE_METHODS: tuple[tuple[str, str, str], ...] = (
    ("avmute", "av_mute", "AV Mute"),
    ("freeze", "freeze", "Freeze"),
    ("infohide", "info_hide", "Information Hide"),
    ("altitude", "high_altitude", "High Altitude"),
    ("keypad", "keypad_lock", "Keypad Lock"),
    ("dismdlocked", "display_mode_lock", "Display Mode Lock"),
    ("directpwon", "direct_power_on", "Direct Power On"),
    ("alwayson", "always_on", "Always On"),
)

# (raw_field, public_name)
_INPUT_METHODS: tuple[tuple[str, str], ...] = (
    ("bright", "brightness"),
    ("contrast", "contrast"),
    ("Sharp", "sharpness"),
    ("Phase", "phase"),
    ("brill", "brilliant_color"),
    ("zoom", "zoom"),
    ("hpos", "horizontal_shift"),
    ("vpos", "vertical_shift"),
    ("autopw", "auto_power_off"),
    ("sleep", "sleep_timer"),
    ("projid", "projector_id"),
)

_TOGGLE_COMMAND_LABELS: dict[str, str] = {
    raw: label for raw, _, label in _TOGGLE_METHODS
}
_TOGGLE_RAW_FIELDS: frozenset[str] = frozenset(raw for raw, _, _ in _TOGGLE_METHODS)
_INPUT_RAW_FIELDS: frozenset[str] = frozenset(raw for raw, _ in _INPUT_METHODS)


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
            **{f"available_{name}": {} for name in _ALL_DROPDOWNS},
            **{f"active_{name}": None for name in _ALL_DROPDOWNS},
            **{name: None for name in _TOGGLE_RAW_FIELDS},
            **{name: None for name in _INPUT_RAW_FIELDS},
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

        dropdowns = set(_ALL_DROPDOWNS)
        for select in soup.find_all("select"):
            key = select.get("id")
            if key in dropdowns:
                options, active = self._parse_drop_down_options(select)
                self.status[f"available_{key}"] = {o["label"]: o["id"] for o in options}
                self.status[f"active_{key}"] = active

        for btn in soup.find_all("td"):
            key = btn.get("id", "")
            if key.endswith("_td"):
                name = key[:-3]
                if name in _TOGGLE_RAW_FIELDS:
                    self.status[name] = btn.get_text().strip() in ("On", "Yes")

        for inp in soup.find_all("input"):
            key = inp.get("id")
            if key in _INPUT_RAW_FIELDS:
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

    # -- Generic accessors --
    def get_available(self, field: str) -> dict[str, int]:
        """Return the mapping of label -> id for a dropdown field."""
        return self.status[f"available_{field}"]

    def get_active(self, field: str) -> str | None:
        """Return the currently selected label for a dropdown field."""
        return self.status[f"active_{field}"]

    async def set_active(self, field: str, value: str) -> None:
        """Select a dropdown value by label, no-op if already active or unavailable."""
        if self.status.get(f"active_{field}") == value:
            return
        available = self.status.get(f"available_{field}") or {}
        if value not in available:
            _LOGGER.warning("Value %r not available for %s", value, field)
            return
        await self._make_request("POST", _CONTROL_PATH, {field: available[value]})
        self.status[f"active_{field}"] = value

    def get_toggle(self, field: str) -> bool | None:
        """Return the cached state of a toggle."""
        return self.status[field]

    async def set_toggle(self, field: str, value: bool) -> None:
        """Set a toggle, refreshing status first if its current state is unknown."""
        if self.status.get(field) is None:
            await self.update_status()
        if self.status.get(field) == value:
            return
        await self._make_request(
            "POST", _CONTROL_PATH, {field: _TOGGLE_COMMAND_LABELS[field]}
        )
        self.status[field] = value

    def get_value(self, field: str) -> int | None:
        """Return the cached numeric value for an input field."""
        return self.status[field]

    async def set_value(self, field: str, value: int) -> None:
        """Send a numeric input value to the projector."""
        await self._make_request("POST", _CONTROL_PATH, {field: value})
        self.status[field] = value

    # -- Power --
    def get_power(self) -> bool | None:
        return self.status["power"]

    async def turn_on(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"btn_powon": "Power On"})
        self.status["power"] = True

    async def turn_off(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"btn_powoff": "Power Off"})
        self.status["power"] = False

    # -- Commands --
    async def resync(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"resync": "Resync"})

    async def reset(self) -> None:
        await self._make_request("POST", _CONTROL_PATH, {"reset": "Reset"})


# Bind the named convenience methods (get_active_source, set_brightness, …) from
# the config tables above.  Generated methods just delegate to the generic
# accessors; the generic API is the source of truth.


def _make_dropdown_methods(
    raw: str,
) -> tuple[
    Callable[[Optoma], dict[str, int]],
    Callable[[Optoma], str | None],
    Callable[[Optoma, str], Awaitable[None]],
]:
    def get_available(self: Optoma) -> dict[str, int]:
        return self.get_available(raw)

    def get_active(self: Optoma) -> str | None:
        return self.get_active(raw)

    async def set_active(self: Optoma, value: str) -> None:
        await self.set_active(raw, value)

    return get_available, get_active, set_active


def _make_toggle_methods(
    raw: str,
) -> tuple[Callable[[Optoma], bool | None], Callable[[Optoma, bool], Awaitable[None]]]:
    def getter(self: Optoma) -> bool | None:
        return self.get_toggle(raw)

    async def setter(self: Optoma, value: bool) -> None:
        await self.set_toggle(raw, value)

    return getter, setter


def _make_input_methods(
    raw: str,
) -> tuple[Callable[[Optoma], int | None], Callable[[Optoma, int], Awaitable[None]]]:
    def getter(self: Optoma) -> int | None:
        return self.get_value(raw)

    async def setter(self: Optoma, value: int) -> None:
        await self.set_value(raw, value)

    return getter, setter


for _raw, _avail_suffix, _active_suffix in _DROPDOWN_METHODS:
    _g_avail, _g_active, _s_active = _make_dropdown_methods(_raw)
    _g_avail.__name__ = f"get_available_{_avail_suffix}"
    _g_active.__name__ = f"get_active_{_active_suffix}"
    _s_active.__name__ = f"set_active_{_active_suffix}"
    setattr(Optoma, _g_avail.__name__, _g_avail)
    setattr(Optoma, _g_active.__name__, _g_active)
    setattr(Optoma, _s_active.__name__, _s_active)

for _raw, _public, _ in _TOGGLE_METHODS:
    _g, _s = _make_toggle_methods(_raw)
    _g.__name__ = f"get_{_public}"
    _s.__name__ = f"set_{_public}"
    setattr(Optoma, _g.__name__, _g)
    setattr(Optoma, _s.__name__, _s)

for _raw, _public in _INPUT_METHODS:
    _g, _s = _make_input_methods(_raw)
    _g.__name__ = f"get_{_public}"
    _s.__name__ = f"set_{_public}"
    setattr(Optoma, _g.__name__, _g)
    setattr(Optoma, _s.__name__, _s)

del _raw, _public, _avail_suffix, _active_suffix, _g, _s, _g_avail, _g_active, _s_active
