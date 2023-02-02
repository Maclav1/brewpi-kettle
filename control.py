#!/usr/bin/python3

import time
import oled
from gpiozero import Button, PWMOutputDevice
from w1thermsensor import W1ThermSensor
import threading
from fastapi import FastAPI, Path
from datetime import datetime, timedelta
from pid import PID
from config import Status, Mode, brauwelt_profile, Conf


status = Status()
app = FastAPI()
stop_threads = False


#########################################################
# OLED Helper - Write status to OLED Screen
def writeScreen():
    text = f"Temp {status.temperature}°C	\n"
    if (status.mode == Mode.AUTOSTART):
        text += "Mash starting at\n"
        text += f"{status.mash_start.strftime('%H:%M')}   \n"
    elif (status.mode == Mode.BRAUWELT):
        text += "Brauwelt Mash       \n"
        text += f"Stage {status.brauwelt_stage + 1} -> {status.setTemp}°C    \n"
    else:
        text += f"SetP {status.setTemp}°C \n"
        text += f"Duty {status.setDuty}%  \n"

    if (status.mode == Mode.OFF):
        text += "Mode: OFF      "
    elif (status.mode == Mode.AUTOSTART):
        text += "Mode: Autostart"
    elif (status.mode == Mode.BRAUWELT):
        text += "Mode: Brauwelt "
    elif (status.mode == Mode.PID):
        text += "Mode: PID      "
    else:
        text += "Mode: DUTY     "

    oledDisplay.writeText(text)
    return text


#########################################################
# button callbacks
def pidUpCall():
    if status.mode == Mode.OFF:
        dtnow = datetime.now()
        day = timedelta(days=1)
        tomorrow = dtnow + day
        status.mash_start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, Conf.autostart_hour, Conf.autostart_min, 0, 0)
    else:
        status.setTemp = status.setTemp + 1
        if (status.setTemp > 100):
            status.setTemp = 100


def pidDownCall():
    if status.mode == Mode.AUTOSTART:
        status.mode = Mode.OFF
        status.mash_start = None
    else:
        status.setTemp = status.setTemp - 1
        if (status.setTemp < 20):
            status.setTemp = 20


def pidUpHold():
    status.setTemp = status.setTemp + 10
    if (status.setTemp > 100):
        status.setTemp = 100


def pidDownHold():
    status.setTemp = status.setTemp - 10
    if (status.setTemp < 20):
        status.setTemp = 20


def dutyUpCall():
    if status.mode == Mode.OFF:
        status.mode = Mode.BRAUWELT
        status.brauwelt_stage = 0
    else:
        status.setDuty = status.setDuty + 1
        if (status.setDuty > 100):
            status.setDuty = 100


def dutyDownCall():
    if status.mode == Mode.BRAUWELT:
        status.mode = Mode.OFF
    else:
        status.setDuty = status.setDuty - 1
        if (status.setDuty < 0):
            status.setDuty = 0


def dutyUpHold():
    status.setDuty = status.setDuty + 10
    if (status.setDuty > 100):
        status.setDuty = 100


def dutyDownHold():
    status.setDuty = status.setDuty - 10
    if (status.setDuty < 0):
        status.setDuty = 0


def dutyOnCall():
    status.mode = Mode.DUTY


def pidOnCall():
    status.mode = Mode.PID


def elementOffCall():
    status.mode = Mode.OFF


#########################################################
# GPIO Elements and Callbacks
ssr = PWMOutputDevice(Conf.GPIO_Kettle)
pid = PID(1, Conf.Kp, Conf.Ki, Conf.Kd)

pidUp = Button(Conf.GLIP_PID_up, hold_repeat=True, hold_time=0.5)
pidUp.when_pressed = pidUpCall
pidUp.when_held = pidUpHold

pidDown = Button(Conf.GLIP_PID_down, hold_repeat=True, hold_time=0.5)
pidDown.when_pressed = pidDownCall
pidDown.when_held = pidDownHold

dutyUp = Button(Conf.GLIP_DUTY_up, hold_repeat=True, hold_time=0.5)
dutyUp.when_pressed = dutyUpCall
dutyUp.when_held = dutyUpHold

dutyDown = Button(Conf.GLIP_DUTY_down, hold_repeat=True, hold_time=0.5)
dutyDown.when_pressed = dutyDownCall
dutyDown.when_held = dutyDownHold


pidOn = Button(Conf.GLIP_PID_on)
pidOn.when_pressed = pidOnCall
pidOn.when_released = elementOffCall

dutyOn = Button(Conf.GLIP_DUTY_on)
dutyOn.when_pressed = dutyOnCall
dutyOn.when_released = elementOffCall

TempProbe = W1ThermSensor()
oledDisplay = oled.oled()


#########################################################
# Temp sensor thread - Run forever. Get temp reading ever second
def read_temp_sensor():
    global stop_threads
    while not stop_threads:
        try:
            if not status.sensor:
                status.sensor = W1ThermSensor()

            status.temperature = round(status.sensor.get_temperature(), 0)
            time.sleep(1)
        except Exception as e:
            print(f"Temp probe not found or error reading probe {e}")
            time.sleep(1)


#########################################################
# Main loop thread - every second update SSR. Update OLED and check for autostart
def ssr_control():
    global stop_threads
    pidTimer = 0
    brauweltTimer = 0
    brauweltRunning = False
    while (not stop_threads):
        if (pidTimer + 1 < time.time()):
            pidTimer = time.time()
            duty = 0  # % of second to run SSR for next timeperiod

            if (status.mode == Mode.OFF):
                ssr.off()
            else:
                if (status.mode == Mode.PID):
                    duty = min(100, max(0, pid.calc(status.temperature, status.setTemp)))
                    print(f"Set element to {duty}")
                elif (status.mode == Mode.DUTY):
                    duty = min(100, max(0, status.setDuty))
                    print(f"Set element to {duty}")
                elif (status.mode == Mode.BRAUWELT):
                    bTable = brauwelt_profile[status.brauwelt_stage]
                    # If runing, wait for timer
                    if (brauweltRunning):
                        runTime = bTable['time'] * 60
                        if (time.time() > brauweltTimer + runTime):
                            status.brauwelt_stage += 1
                            brauweltRunning = False
                            print(f"End stage {status.brauwelt_stage}")
                        else:
                            duty = min(100, max(0, pid.calc(status.temperature, status.setTemp)))
                            print(f"Holding to {status.setTemp}/{status.temperature} Set element to {duty}")
                    # Not running, ramp up and start
                    else:
                        # Start step
                        if (bTable['temp'] - 1 <= status.temperature <= bTable['temp'] + 1):
                            brauweltTimer = time.time()
                            brauweltRunning = True
                            print(f"At target {bTable['temp']} Start hold time")
                        # Heat to step
                        else:
                            status.setTemp = bTable['temp']
                            duty = min(100, max(0, pid.calc(status.temperature, status.setTemp)))
                            print(f"Heat to {status.setTemp}/{status.temperature} Set element to {duty}")

                    duty = duty / 100
                    ssr.blink(duty, 1 - duty)

        if (status.mode == Mode.AUTOSTART and status.mash_start and status.mash_start <= datetime.now()):
            status.setTemp = Conf.autostart_temp
            status.mode = Mode.PID
            status.mash_start = None
            print("Mash Started\n")

        writeScreen()


#########################################################
# Loop threads for temp probe and ssr control
tempThread = threading.Thread(target=read_temp_sensor)
ssrThread = threading.Thread(target=ssr_control)


#########################################################
# FastAPI events
@app.on_event("startup")
async def startup_event():
    tempThread.start()
    ssrThread.start()


@app.on_event("shutdown")
def shutdown_event():
    global stop_threads
    stop_threads = True
    tempThread.join()
    ssrThread.join()


@app.get("/")
async def getStatus():
    return status


@app.post("/mode/{mode}")
async def postMode(mode: Mode):
    status.mode = mode
    ssr.off()
    if status.mode == Mode.BRAUWELT:
        status.brauwelt_stage = 0

    if status.mode == Mode.AUTOSTART:
        dtnow = datetime.now()
        day = timedelta(days=1)
        tomorrow = dtnow + day
        status.mash_start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 30, 0, 0)
    else:
        status.mash_start = None

    return status


@app.post("/temp/{t}")
async def postTemp(t: int = Path(gt=0, le=100)):
    status.setTemp = t
    return status


@app.post("/duty/{d}")
async def postStatus(d: int = Path(ge=0, le=100)):
    status.setDuty = d
    return status


@app.post("/date/{d}")
async def postDate(d: datetime):
    status.mash_start = d
    return status
