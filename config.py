from enum import IntEnum
from pydantic import BaseModel
from datetime import datetime
from typing import Any

## Defaults
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
	Kp: int = 20
	Ki: int = 1
	Kd: int = 40
	setTemp: int = 70
	setDuty: int = 100
	sensor: Any = None
	temperature: float = 0.0
	mash_start: datetime = None
	brauwelt_stage: int = 0


