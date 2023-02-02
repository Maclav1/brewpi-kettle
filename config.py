from enum import IntEnum
from pydantic import BaseModel
from datetime import datetime
from typing import Any


class Mode(IntEnum):
    OFF = 0
    PID = 1
    DUTY = 2
    BRAUWELT = 3
    AUTOSTART = 4


brauwelt_profile = [
    {'temp': 62, 'time': 20},
    {'temp': 64, 'time': 20},
    {'temp': 67, 'time': 20},
    {'temp': 72, 'time': 20},
    {'temp': 76, 'time': 9999}
]


class Status(BaseModel):
    mode: Mode = Mode.OFF
    setTemp: int = 70
    setDuty: int = 100
    sensor: Any = None
    temperature: float = 0.0
    mash_start: datetime = None
    brauwelt_stage: int = 0


class Conf():
    # OLED Settings
    oled_addr: int = 0x3C
    oled_height: int = 64
    oled_width: int = 128
    oled_font: str = "/DejaVuSansMono.ttf"
    oled_font_size: int = 14

    # PID Settiongs
    Kp: int = 20
    Ki: int = 1
    Kd: int = 40

    # GPIOs
    GPIO_Kettle: str = "GPIO24"
    GLIP_PID_up: str = "GPIO14"
    GLIP_PID_down: str = "GPIO4"
    GLIP_DUTY_up: str = "GPIO15"
    GLIP_DUTY_down: str = "GPIO17"
    GLIP_PID_on: str = "GPIO23"
    GLIP_DUTY_on: str = "GPIO22"

    # Misc
    autostart_hour: int = 6
    autostart_min: int = 0
    autostart_temp: int = 60
