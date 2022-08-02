import hashlib

import httpx
from bs4 import BeautifulSoup


class Optoma:
    def __init__(self, base_url: str, username: str = "admin", password: str = "admin"):
        self.http = httpx.AsyncClient()
        self.base_url = base_url
        self.username = username
        self.password = password
        self.status = {
            "available_source": {},
            "active_source": None,
            "available_colortmp": {},
            "active_colortmp": None,
            "available_dismode0": {},
            "active_dismode0": None,
            "available_dismode1": {},
            "active_dismode1": None,
            "available_colorsp0": {},
            "active_colorsp0": None,
            "available_colorsp1": {},
            "active_colorsp1": None,
            "available_aspect0": {},
            "active_aspect0": None,
            "available_aspect1": {},
            "active_aspect1": None,
            "available_screen": {},
            "active_screen": None,
            "available_projection": {},
            "active_projection": None,
            "available_background": {},
            "active_background": None,
            "available_wall": {},
            "active_wall": None,
            "available_logo": {},
            "active_logo": None,
            "available_pwmode": {},
            "active_pwmode": None,
            "available_lampmd": {},
            "active_lampmd": None,
            "avmute": None,
            "freeze": None,
            "infohide": None,
            "altitude": None,
            "keypad": None,
            "dismdlocked": None,
            "directpwon": None,
            "alwayson": None,
            "bright": None,
            "contrast": None,
            "brill": None,
            "zoom": None,
            "hpos": None,
            "vpos": None,
            "autopw": None,
            "sleep": None,
            "projid": None,
            "power": None,
        }

    async def _make_request(self, method, path, data=None):
        response = await self.http.request(method, f"{self.base_url}{path}", data=data)
        return response

    async def login(self):
        response = await self.http.get(f"{self.base_url}/login.htm")
        soup = BeautifulSoup(response.text, "html.parser")
        challenge_element = soup.find("input", {"name": "Challenge"})
        if challenge_element is None:
            return False

        challenge = challenge_element["value"]
        login_str = self.username + self.password + challenge
        response = hashlib.md5(login_str.encode())
        data = {
            "user": 0,
            "Username": "1",
            "Password": "",
            "Challenge": "",
            "Response": response.hexdigest(),
        }

        response = await self.http.post(f"{self.base_url}/tgi/login.tgi", data=data)
        if response.status_code != 200:
            return

        await self.update_status()

    def _parse_drop_down_options(self, select_element: BeautifulSoup):
        option_elements = select_element.find_all("option")
        options = []
        selected = None
        for option_element in option_elements:
            label = option_element.get_text().replace("\n", " ")
            options.append(
                {"id": int(option_element["value"]), "label": label.replace(".", "")}
            )
            if option_element.has_attr("selected"):
                selected = label

        return sorted(options, key=lambda i: i["id"]), selected

    async def update_status(self):
        dropdowns = [
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
        ]
        toggle_buttons = [
            "avmute_td",
            "freeze_td",
            "infohide_td",
            "altitude_td",
            "keypad_td",
            "dismdlocked_td",
            "directpwon_td",
            "alwayson_td",
        ]
        inputs = [
            "bright",
            "contrast",
            "Sharp" "Phase",
            "brill",
            "zoom",
            "hpos",
            "vpos",
            "autopw",
            "sleep",
            "projid",
        ]

        response = await self._make_request("GET", "/control.htm")
        soup = BeautifulSoup(response.text, "html.parser")

        for select in soup.find_all("select"):
            if select.has_attr("id") and select["id"] in dropdowns:
                options, active = self._parse_drop_down_options(select)
                for option in options:
                    if f"available_{select['id']}" not in self.status:
                        self.status[f"available_{select['id']}"] = {}
                    self.status[f"available_{select['id']}"][option["label"]] = option[
                        "id"
                    ]
                self.status[f"active_{select['id']}"] = active

        for btn in soup.find_all("td"):
            if btn.has_attr("id") and btn["id"] in toggle_buttons:
                label = btn.get_text().replace("\n", "")
                self.status[f"{btn['id'].replace('_td', '')}"] = (
                    True if label == "On" or label == "Yes" else False
                )

        for input in soup.find_all("input"):
            if input.has_attr("id") and input["id"] in inputs:
                self.status[input["id"]] = int(input["value"])

        power_on_button = soup.find("input", {"id": "pwr"})
        self.status["power"] = True if int(power_on_button["value"]) == 1 else False

    async def get_available_sources(self):
        return self.status["available_source"]

    async def get_active_source(self):
        return self.status["active_source"]

    async def set_active_source(self, value: str):
        if self.status["active_source"] == value:
            return

        if value not in self.status["available_source"]:
            return

        command = {"source": self.status["available_source"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_source"] = value

    async def get_available_dismodes_0(self):
        return self.status["available_dismode0"]

    async def get_active_dismode_0(self):
        return self.status["active_dismode0"]

    async def set_active_dismode_0(self, value: str):
        if self.status["active_dismode0"] == value:
            return

        if value not in self.status["available_dismode0"]:
            return

        command = {"dismode0": self.status["available_dismode0"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_dismode0"] = value

    async def get_available_dismodes_1(self):
        return self.status["available_dismode1"]

    async def get_active_dismode_1(self):
        return self.status["active_dismode1"]

    async def set_active_dismode_1(self, value: str):
        if self.status["active_dismode1"] == value:
            return

        if value not in self.status["available_dismode1"]:
            return

        command = {"dismode1": self.status["available_dismode1"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_dismode1"] = value

    async def get_available_colorsps_0(self):
        return self.status["available_colorsp0"]

    async def get_active_colorsp_0(self):
        return self.status["active_colorsp0"]

    async def set_active_colorsp_0(self, value: str):
        if self.status["active_colorsp0"] == value:
            return

        if value not in self.status["available_colorsp0"]:
            return

        command = {"colorsp0": self.status["available_colorsp0"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_colorsp0"] = value

    async def get_available_colorsps_1(self):
        return self.status["available_colorsp1"]

    async def get_active_colorsp_1(self):
        return self.status["active_colorsp1"]

    async def set_active_colorsp_1(self, value: str):
        if self.status["active_colorsp1"] == value:
            return

        if value not in self.status["available_colorsp1"]:
            return

        command = {"colorsp1": self.status["available_colorsp1"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_colorsp1"] = value

    async def get_available_gammas(self):
        return self.status["available_Degamma"]

    async def get_active_gamma(self):
        return self.status["active_Degamma"]

    async def set_active_gamma(self, value: str):
        if self.status["active_Degamma"] == value:
            return

        if value not in self.status["available_Degamma"]:
            return

        command = {"Degamma": self.status["available_Degamma"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_Degamma"] = value

    async def get_available_brightness_modes(self):
        return self.status["available_lampmd"]

    async def get_active_brightness_mode(self):
        return self.status["active_lampmd"]

    async def set_active_brightness_mode(self, value: str):
        if self.status["active_lampmd"] == value:
            return

        if value not in self.status["available_lampmd"]:
            return

        command = {"lampmd": self.status["available_lampmd"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_lampmd"] = value

    async def get_available_color_temperature(self):
        return self.status["available_colortmp"]

    async def get_active_color_temperature(self):
        return self.status["active_colortmp"]

    async def set_active_color_temperature(self, value: str):
        if self.status["active_colortmp"] == value:
            return

        if value not in self.status["available_colortmp"]:
            return

        command = {"colortmp": self.status["available_colortmp"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)

    async def get_available_logo(self):
        return self.status["available_logo"]

    async def get_active_logo(self):
        return self.status["active_logo"]

    async def set_active_logo(self, value: str):
        if self.status["active_logo"] == value:
            return

        if value not in self.status["available_logo"]:
            return

        command = {"logo": self.status["available_logo"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["active_logo"] = value

    async def get_available_power_modes(self):
        return self.status["available_pwmode"]

    async def get_active_power_mode(self):
        return self.status["active_pwmode"]

    async def set_active_power_mode(self, value: str):
        if self.status["active_pwmode"] == value:
            return

        if value not in self.status["available_pwmode"]:
            return

        command = {"pwmode": self.status["available_pwmode"][value]}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["pwmode"] = value

    async def get_info_hide(self):
        return self.status["infohide"]

    async def set_info_hide(self, value: bool):
        if self.status["infohide"] == value:
            return

        command = {"infohide": "Information Hide"}

        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["infohide"] = value

    async def get_always_on(self):
        return self.status["alwayson"]

    async def set_always_on(self, value: bool):
        if self.status["alwayson"] == value:
            return

        command = {"alwayson": "Always On"}

        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["alwayson"] = value

    async def resync(self):
        command = {"resync": "Resync"}
        await self._make_request("post", "/tgi/control.tgi", command)

    async def get_zoom(self):
        return self.status["zoom"]

    async def set_zoom(self, value: int):
        command = {"zoom": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["zoom"] = value

    async def get_horizontal_shift(self):
        return self.status["hpos"]

    async def set_horizontal_shift(self, value: int):
        command = {"hpos": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["hpos"] = value

    async def get_vertical_shift(self):
        return self.status["vpos"]

    async def set_vertical_shift(self, value: int):
        command = {"vpos": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["vpos"] = value

    async def get_auto_power_off(self):
        return self.status["autopw"]

    async def set_auto_power_off(self, value: int):
        command = {"autopw": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["autopw"] = value

    async def get_sleep_timer(self) -> int:
        return self.status["sleep"]

    async def set_sleep_timer(self, value: int):
        command = {"sleep": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["sleep"] = value

    async def get_projector_id(self):
        return self.status["projid"]

    async def set_projector_id(self, value: int):
        command = {"projid": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["projid"] = value

    async def get_brightness(self):
        return self.status["bright"]

    async def set_brightness(self, value: int):
        command = {"bright": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["bright"] = value

    async def get_contrast(self):
        return self.status["contrast"]

    async def set_contrast(self, value: int):
        command = {"contrast": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["contrast"] = value

    async def get_sharpness(self):
        return self.status["Sharp"]

    async def set_sharpness(self, value: int):
        command = {"Sharp": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["Sharp"] = value

    async def get_phase(self):
        return self.status["Phase"]

    async def set_phase(self, value: int):
        command = {"Phase": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["Phase"] = value

    async def get_brilliant_color(self):
        return self.status["brill"]

    async def set_brilliant_color(self, value: int):
        command = {"brill": value}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["brill"] = value

    async def get_freeze(self):
        return self.status["freeze"]

    async def set_freeze(self, value: bool):
        if self.status["freeze"] == value:
            return

        command = {"freeze": "Freeze"}

        await self._make_request("post", "/tgi/control.tgi", command)

        self.status["freeze"] = value

    async def get_av_mute(self):
        return self.status["avmute"]

    async def set_av_mute(self, value: bool):
        if self.status["avmute"] == value:
            return
        command = {"avmute": "AV Mute"}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["avmute"] = value

    async def get_high_altitude(self):
        return self.status["altitude"]

    async def set_high_altitude(self, value: bool):
        if self.status["altitude"] == value:
            return
        command = {"altitude": "High Altitude"}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["altitude"] = value

    async def get_keypad_lock(self):
        return self.status["keypad"]

    async def set_keypad_lock(self, value: bool):
        if self.status["keypad"] == value:
            return
        command = {"keypad": "Keypad Lock"}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["keypad"] = value

    async def get_display_mode_lock(self):
        return self.status["dismdlocked"]

    async def set_display_mode_lock(self, value: bool):
        if self.status["dismdlocked"] == value:
            return
        command = {"dismdlocked": "Display Mode Lock"}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["dismdlocked"] = value

    async def get_direct_power_on(self):
        return self.status["directpwon"]

    async def set_direct_power_on(self, value: bool):
        if self.status["directpwon"] == value:
            return
        command = {"directpwon": "Direct Power On"}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["directpwon"] = value

    async def reset(self):
        command = {"reset": "Reset"}
        await self._make_request("post", "/tgi/control.tgi", command)

    async def get_power(self):
        return self.status["power"]

    async def turn_on(self):
        command = {"btn_powon": "Power On"}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["power"] = True

    async def turn_off(self):
        command = {"btn_powoff": "Power Off"}
        await self._make_request("post", "/tgi/control.tgi", command)
        self.status["power"] = False
