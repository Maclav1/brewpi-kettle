#!/usr/bin/python3

import time
import oled
import time
from gpiozero import Button, PWMOutputDevice
from w1thermsensor import W1ThermSensor
import threading
from fastapi import FastAPI
from datetime import datetime, timedelta
from pid import PID
from config import Status, Mode, brauwelt_profile



## Setup temp reader
status = Status()
app = FastAPI()
stop_threads = False

# Sensor thread
def read_temp_sensor():
	global stop_threads
	while not stop_threads:
		try:
			if not status.sensor:
				status.sensor = W1ThermSensor()
			
			status.temperature = round(status.sensor.get_temperature(), 0)
			time.sleep(5)  
		except Exception as e:
			print (f"Temp probe not found or error reading probe {e}") 
			time.sleep(1)						

## Kettle control
# 18 - GPIO24 -> Kettle SSR
ssr = PWMOutputDevice("GPIO24")
pid = PID(1,status.Kp,status.Ki,status.Kd)

## OLED Helper
def writeScreen():
	text =  f"Temp {status.temperature}°C	\n"
	if (status.mode == Mode.AUTOSTART):
		text += f"Mash starting at\n"
		text += f"{status.mash_start.strftime('%H:%M')}   \n"
	elif (status.mode == Mode.BRAUWELT):
		text += f"Brauwelt Mash       \n"
		text += f"Stage {status.brauwelt_stage + 1} -> {status.setTemp}°C    \n"
	else:			
		text += f"SetP {status.setTemp}°C \n"
		text += f"Duty {status.setDuty}%  \n"
		
	if (status.mode == Mode.OFF):
		text += f"Mode: OFF      "
	elif (status.mode == Mode.AUTOSTART):
		text += f"Mode: Autostart"		
	elif (status.mode == Mode.BRAUWELT):
		text += f"Mode: Brauwelt "
	elif (status.mode == Mode.PID):
		text += f"Mode: PID      "
	else:
		text += f"Mode: DUTY     "
			
	oledDisplay.writeText(text)
	return text
	
## button callbacks
def pidUpCall():
	if status.mode == Mode.OFF:	
		dtnow = datetime.now()
		day = timedelta(days=1)
		tomorrow = dtnow + day
		status.mash_start = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 30, 0, 0)	  
	else:
		status.setTemp = status.setTemp +1
		if (status.setTemp > 100):
			status.setTemp = 100	   
	#print ("PID +")
	
def pidDownCall():
	if status.mode == Mode.AUTOSTART:		
		status.mode = Mode.OFF
		status.mash_start = None	
	else:	
		status.setTemp = status.setTemp -1
		if (status.setTemp < 20):
			status.setTemp = 20  
   # print ("PID -")

def pidUpHold():
	status.setTemp = status.setTemp +10
	if (status.setTemp > 100):
		status.setTemp = 100	  
	#print ("PID +")
		
def pidDownHold():
	status.setTemp = status.setTemp -10
	if (status.setTemp < 20):
		status.setTemp = 20	
	#print ("PID -")
	
def dutyUpCall():
	if status.mode == Mode.OFF:
		status.mode = Mode.BRAUWELT
		status.brauwelt_stage = 0
	else:
		status.setDuty = status.setDuty +1
		if (status.setDuty > 100):
			status.setDuty = 100
	#print ("Duty +")
	
def dutyDownCall():
	if status.mode == Mode.BRAUWELT:
		status.mode = Mode.OFF
	else:   
		status.setDuty = status.setDuty -1
		if (status.setDuty < 0):
			status.setDuty = 0	
   # print ("Duty -")
	
def dutyUpHold():
	status.setDuty = status.setDuty +10
	if (status.setDuty > 100):
		status.setDuty = 100	
	#print ("Duty +")
	
def dutyDownHold():
	status.setDuty = status.setDuty -10
	if (status.setDuty < 0):
		status.setDuty = 0	  
	#print ("Duty -")	
	
def dutyOnCall():
	status.mode = Mode.DUTY

def pidOnCall():
	status.mode = Mode.PID

def elementOffCall():
	status.mode = Mode.OFF
	ssr.off()

## setup pins
# 16 - GPIO23 -> PID On
# 15 - GPIO22 -> DUTY On

# 8  - GPIO14 -> PID Temp+
# 7  - GPIO4  -> PID Temp-

# 10 - GPIO15 -> Duty+
# 11 - GPIO17 -> Duty-
pidUp = Button("GPIO14", hold_repeat=True, hold_time=0.5) 
pidUp.when_pressed = pidUpCall
pidUp.when_held = pidUpHold

pidDown = Button("GPIO4", hold_repeat=True, hold_time=0.5) 
pidDown.when_pressed = pidDownCall
pidDown.when_held = pidDownHold

dutyUp = Button("GPIO15", hold_repeat=True, hold_time=0.5) 
dutyUp.when_pressed = dutyUpCall
dutyUp.when_held = dutyUpHold

dutyDown = Button("GPIO17", hold_repeat=True, hold_time=0.5) 
dutyDown.when_pressed = dutyDownCall
dutyDown.when_held = dutyDownHold


pidOn = Button("GPIO23") 
pidOn.when_pressed = pidOnCall
pidOn.when_released = elementOffCall

dutyOn = Button("GPIO22")
dutyOn.when_pressed = dutyOnCall
dutyOn.when_released = elementOffCall

TempProbe = W1ThermSensor() #get_temperature()
oledDisplay = oled.oled()


# Main loop, refresh PID every second
def main_loop():
	global stop_threads
	pidTimer = 0
	brauweltTimer = 0
	brauweltRunning = False
	while (not stop_threads):  
		# Once a second
		if (pidTimer + 1 < time.time()):
			duty = 0
			if (status.mode == Mode.PID):
				duty = min(100, max(0, pid.calc(status.temperature, status.setTemp)))
				print (f"Set element to {duty}")
			elif (status.mode == Mode.DUTY):
				duty = min(100, max(0, status.setDuty))
				print (f"Set element to {duty}")
			elif (status.mode == Mode.BRAUWELT):
				bTable = brauwelt_profile[status.brauwelt_stage]
				# If runing, wait for timer
				if (brauweltRunning):
					runTime = bTable['time'] * 60
					if (time.time() > brauweltTimer + runTime):
						status.brauwelt_stage += 1
						brauweltRunning = False
						print (f"End stage {status.brauwelt_stage}")
					else:
						duty = min(100, max(0, pid.calc(status.temperature, status.setTemp)))
						print (f"Holding to {status.setTemp}/{status.temperature} Set element to {duty}")						
				# Not running, ramp up and start
				else:
					# Start step
					if (bTable['temp'] -1 <= status.temperature <= bTable['temp'] +1):				
						brauweltTimer = time.time()
						brauweltRunning = True
						print (f"At target {bTable['temp']} Start hold time")	
					# Heat to step
					else:
						status.setTemp = bTable['temp']
						duty = min(100, max(0, pid.calc(status.temperature, status.setTemp)))
						print (f"Heat to {status.setTemp}/{status.temperature} Set element to {duty}")		
		
			duty = duty / 100
			ssr.blink(duty, 1 - duty)		 
			pidTimer = time.time()

		if (status.mode == Mode.AUTOSTART and status.mash_start and status.mash_start <= datetime.now()):
			status.setTemp = 60
			status.mode = Mode.PID	
			status.mash_start = None
			print("Mash Started\n")
			
		writeScreen()
		#time.sleep(0.1)

tempThread = threading.Thread(target=read_temp_sensor)
mainThread = threading.Thread(target=main_loop)

@app.on_event("startup")
async def startup_event():
	tempThread.start()
	mainThread.start()

@app.on_event("shutdown")
def shutdown_event():
	global stop_threads
	stop_threads = True
	tempThread.join()
	mainThread.join()

@app.get("/")
async def getStatus():
    return status

# @app.post("/state/")
# async def postState(s: Status):
# 	print(s)

# 	status.setTemp = s.setTemp
# 	if status.mode == Mode.AUTOSTART:
# 		status.mash_start = s.mash_start
# 	status.setDuty = s.setDuty

# 	return status

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
async def postTemp(t: int):
	status.setTemp = t
	return status
	
@app.post("/duty/{d}")
async def postStatus(d: int):
	status.setDuty = d
	return status

@app.post("/date/{d}")
async def postTemp(d: datetime):
	status.mash_start = d
	return status

# # def do_app():

# docker run -v /sys:/sys  -P --privileged brewpi


# 	time = flask.request.form.get("startmash")
# 	clear = flask.request.form.get("clear")   
# 	set = flask.request.form.get("set")  

# 	print(f"{flask.request.form}")

# 	if clear:
# 		status.mash_start = None
# 		status.brauwelt_stage = 0
# 		brauwelt_target = 0
# 	if set:
# 		status.mash_start = datetime.fromisoformat(time)

# 	if status.mash_start:
# 		time = status.mash_start.isoformat()
# 	else:
# 		dtnow = datetime.now()
# 		day = timedelta(days=1)
# 		tomorrow = dtnow + day
# 		settime = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 6, 30, 0, 0)
# 		time = settime.isoformat()
	
# 	html = f"<html><head></head><body>"
# 	if (status.mash_start):
# 		html += f"<p>Current Set Time: {time} start mash at 65c on PID</p>"
# 	html += f"<a href=/><button>Refresh</button></a><br>"
# 	html += f"<form method='POST'><input type='datetime-local' id='startmash' name='startmash' value='{time}'>"
# 	html += f"<input type='submit' id='clear' name='clear' value='Clear Mash''/>"
# 	html += f"<input type='submit' id='set' name='set' value='Set Mash Start'/></form>"
# 	html += f"<br><hr><p>{writeScreen()}</p>"
# 	html += "</body></html>"

# 	return html


	   
	
	





