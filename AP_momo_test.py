import numpy as np
from numpy import pi
import socket
import struct
import pickle
import time
import os
import json
os.environ["MAVLINK20"] = "2"
from apscheduler.schedulers.background import BackgroundScheduler
from dronekit import connect, VehicleMode
from pymavlink import mavutil
import subprocess

# FCU connection variables
vehicle = None
is_vehicle_connected = False

global rover_status

cur_lat = 0.0
cur_lon = 0.0
cur_yaw = 0.0
gps_status = 0

rover_status = {"lat" : cur_lat, "lng" : cur_lon, "yaw" : cur_yaw, "gps" : gps_status}
out_file_path = "/home/nvidia/ATCart-momo/rover_status.txt"

def vehicle_connect():
	global vehicle, is_vehicle_connected

	if vehicle == None:
		try:
			print("Connecting to Ardupilot....")
			vehicle = connect('/dev/ttyUSB0', wait_ready=True, baud=921600)
		except:
			print('Connection error! Retrying...')
			vehicle = connect('/dev/ttyUSB1', wait_ready=True, baud=921600)
			time.sleep(1)

	if vehicle == None:
		is_vehicle_connected = False
		return False
	else:
		is_vehicle_connected = True
		return True

def turn(deg):
	if is_vehicle_connected == True:
		msg = vehicle.message_factory.set_position_target_local_ned_encode(
			0,       # time_boot_ms (not used)
			0, 0,    # target system, target component
			mavutil.mavlink.MAV_FRAME_BODY_NED, # frame
			0b0000101111111111, # type_mask (only speeds enabled)
			0, 0, 0, # x, y, z positions (not used)
			0, 0, 0, # x, y, z velocity in m/s
			0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
			deg*pi/180.0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)

		vehicle.send_mavlink(msg)
		# vehicle.flush()
	else:
		print("INFO: Vehicle not connected.")

def goForward(meter):
	if is_vehicle_connected == True:
		msg = vehicle.message_factory.set_position_target_local_ned_encode(
			0,       # time_boot_ms (not used)
			0, 0,    # target system, target component
			mavutil.mavlink.MAV_FRAME_BODY_NED, # frame
			0b0000111111111000, # type_mask (only speeds enabled)
			meter, 0, 0, # x, y, z positions (not used)
			0, 0, 0, # x, y, z velocity in m/s
			0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
			0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)
			
		vehicle.send_mavlink(msg)
		# vehicle.flush()
	else:
		print("INFO: Vehicle not connected.")

def goLeft(meter):
	if is_vehicle_connected == True:
		msg = vehicle.message_factory.set_position_target_local_ned_encode(
			0,       # time_boot_ms (not used)
			0, 0,    # target system, target component
			mavutil.mavlink.MAV_FRAME_BODY_NED, # frame
			0b0000111111111000, # type_mask (only speeds enabled)
			0, -meter, 0, # x, y, z positions (not used)
			0, 0, 0, # x, y, z velocity in m/s
			0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
			0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)
			
		vehicle.send_mavlink(msg)
		# vehicle.flush()
	else:
		print("INFO: Vehicle not connected.")

def goRight(meter):
	if is_vehicle_connected == True:
		msg = vehicle.message_factory.set_position_target_local_ned_encode(
			0,       # time_boot_ms (not used)
			0, 0,    # target system, target component
			mavutil.mavlink.MAV_FRAME_BODY_NED, # frame
			0b0000111111111000, # type_mask (only speeds enabled)
			0, meter, 0, # x, y, z positions (not used)
			0, 0, 0, # x, y, z velocity in m/s
			0, 0, 0, # x, y, z acceleration (not supported yet, ignored in GCS_Mavlink)
			0, 0)    # yaw, yaw_rate (not supported yet, ignored in GCS_Mavlink)
			
		vehicle.send_mavlink(msg)
		# vehicle.flush()
	else:
		print("INFO: Vehicle not connected.")


def read_socat(term):
	read = term.readline().decode()
	return read

# Callback to print the location in global frame
def location_callback(self, attr_name, value):
	# global cur_lat, cur_lon
	cur_lat = value.global_frame.lat
	cur_lon = value.global_frame.lon
	# print("cur_lat: %.7f  cur_lon: %.7f" %(cur_lat, cur_lon))
	rover_status['lat'] = cur_lat
	rover_status['lng'] = cur_lon
	
	# print(value.global_frame)

def attitude_callback(self, attr_name, value):
	# global cur_yaw
	cur_yaw = value.yaw
	# print("cur_yaw: %.6f" %cur_yaw)
	rover_status['yaw'] = cur_yaw
	## range is -pi to pi, 0 is north

def gps_callback(self, attr_name, value):
	# global gps_status
	gps_status = value.fix_type
	# print("gps_status: %d" %gps_status)
	rover_status['gps'] = gps_status
	# 3 = 3DFix
	# 4 = 3DGPS
	# 5 = rtkFloat
	# 6 = rtkFixed
	## range is -pi to pi, 0 is north


print("INFO: Connecting to vehicle.")
while (not vehicle_connect()):
	pass
print("INFO: Vehicle connected.")

vehicle.mode = "HOLD"
current_mode = "HOLD"
vehicle.armed= False

#BUTTONS:
# 0 A   		AUTO
# 1 B   		HOLD
# 2 X   		MANUAL
# 3 Y   		ARMDISARM
# 4 LB  		left 45
# 5 RB  		right 45 
# 6 LT  		left 90
# 7 RT  		right 90
# 16 Logicool   turn 180

#AXES
# Axis1 left stick up down
# Axis2 right stick left right

vehicle.add_attribute_listener('location', location_callback)
vehicle.add_attribute_listener('attitude', attitude_callback)
vehicle.add_attribute_listener('gps_0', gps_callback)

PORT = "/dev/pts/1"

prev_arm_state = 0
prev_mode = 'NONE'

with open(PORT, "rb", buffering=0) as term:

	print("begin")
	while True:
		# print(term)
		try:
			str_buffer = read_socat(term)

			dec = json.loads(str_buffer)
			# print("Here")
			## Joystick input
			# print(str_buffer)
			if len(str_buffer) > 400:
				### Mode / Armed ###
				if dec["BUTTONS"]["#02"] == 1 or (dec["MODE"] != prev_mode and dec["MODE"] == "MANUAL"):
					if current_mode != "MANUAL":
						vehicle.mode = "MANUAL"
					current_mode = "MANUAL"
					print("MANUAL")

				elif dec["BUTTONS"]["#01"] == 1 or (dec["MODE"] != prev_mode and dec["MODE"] == "HOLD"):
					if current_mode != "HOLD":
						vehicle.mode = "HOLD"
					current_mode = "HOLD"
					print("HOLD")

				elif dec["BUTTONS"]["#00"] == 1 or (dec["MODE"] != prev_mode and dec["MODE"] == "AUTO"):
					if current_mode != "AUTO":
						vehicle.mode = "AUTO"
					current_mode = "AUTO"
					print("AUTO")

				elif dec["BUTTONS"]["#03"] == 1 or int(dec['ARMED']) != prev_arm_state:
					if vehicle.armed == True:
						vehicle.armed= False
					else:
						vehicle.armed = True
					print("ARMDISARM")	

				### Direction Control ###
				if dec["BUTTONS"]["#04"] == 1 or dec["TURN_DIR"] == "TURNLEFT45":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(-45)
					print("TURNLEFT45")

				elif dec["BUTTONS"]["#06"] == 1 or dec["TURN_DIR"] == "TURNLEFT90":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(-90)
					print("TURNLEFT90")

				elif dec["BUTTONS"]["#05"] == 1 or dec["TURN_DIR"] == "TURNRIGHT45":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(45)
					print("TURNRIGHT45")

				elif dec["BUTTONS"]["#07"] == 1 or dec["TURN_DIR"] == "TURNRIGHT90":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(90)
					print("TURNRIGHT90")

				elif dec["BUTTONS"]["#16"] == 1 or dec["TURN_DIR"] == "TURN180":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(180)	
					print("TURN180")

				elif dec["FORWARD"] != 0:
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					goForward(int(dec["FORWARD"]))	
					print("GOFORWARD")

				elif dec["LEFT"] != 0:
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					goLeft(int(dec["LEFT"]))	
					print("GOLEFT")

				elif dec["RIGHT"] != 0:
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					goRight(int(dec["RIGHT"]))	
					print("GORIGHT")


				if current_mode == "MANUAL":
					STR_val = dec["AXES"]["#02"]
					THR_val = (-1)*dec["AXES"]["#01"]

					steering_pwm = int(round(STR_val*200 + 1500))
					throttle_pwm = int(round(THR_val*200 + 1500))
					vehicle.channels.overrides['1'] = steering_pwm
					vehicle.channels.overrides['2'] = throttle_pwm
				else:
					vehicle.channels.overrides['1'] = 1500
					vehicle.channels.overrides['2'] = 1500

				prev_mode = dec["MODE"]
				prev_arm_state = dec['ARMED']
			
			else:
				# print(str_buffer)
				if (dec["MODE"] == "MANUAL"):
					if current_mode != "MANUAL":
						vehicle.mode = "MANUAL"

					current_mode = "MANUAL"
					print("WITHOUT_GAMEPAD : MANUAL")

				elif (dec["MODE"] == "AUTO"):
					if current_mode != "AUTO":
						vehicle.mode = "AUTO"

					current_mode = "AUTO"
					print("WITHOUT_GAMEPAD : AUTO")

				elif (dec["MODE"] == "HOLD"):
					if current_mode != "HOLD":
						vehicle.mode = "HOLD"

					current_mode = "HOLD"
					print("WITHOUT_GAMEPAD : HOLD")




				if (int(dec['ARMED']) != prev_arm_state):
					if vehicle.armed == True:
						vehicle.armed= False
					else:
						vehicle.armed = True
					print("WITHOUT_GAMEPAD : ARMDISARM")

				
				prev_arm_state = dec['ARMED']




				if dec["TURN_DIR"] == "TURNLEFT45":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(-45)
					print("WITHOUT_GAMEPAD : TURNLEFT45")

				elif dec["TURN_DIR"] == "TURNLEFT90":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(-90)
					print("WITHOUT_GAMEPAD : TURNLEFT90")

				elif dec["TURN_DIR"] == "TURNRIGHT45":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(45)
					print("WITHOUT_GAMEPAD : TURNRIGHT45")

				elif dec["TURN_DIR"] == "TURNRIGHT90":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(90)
					print("WITHOUT_GAMEPAD : TURNRIGHT90")

				elif dec["TURN_DIR"] == "TURN180":
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					turn(180)	
					print("WITHOUT_GAMEPAD : TURN180")


				elif dec["FORWARD"] != 0:
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					goForward(int(dec["FORWARD"]))	
					print("GOFORWARD")

				elif dec["LEFT"] != 0:
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					goLeft(int(dec["LEFT"]))	
					print("GOLEFT")

				elif dec["RIGHT"] != 0:
					if current_mode != "GUIDED":
						vehicle.mode = "GUIDED"
						current_mode = "GUIDED"
					goRight(int(dec["RIGHT"]))	
					print("GORIGHT")



			# with open("rover_status.json", "w") as out_file:
			# 	json.dump(rover_status, out_file)
			# 	cmd1 = 'echo $(cat rover_status.json) >> /dev/pts/6'
			# 	subprocess.run(cmd1, shell = True)

			## Open file and overwrite it everytime
			file = open(out_file_path, "w+")
			json_data = json.dumps(rover_status)
			file.write(json_data)
			cmd1 = 'echo $(cat rover_status.txt) > {:s}'.format(PORT)
			subprocess.run(cmd1, shell = True)
			# print("send ", rover_status)

			# print("sent data back")
			# print('Down herer')

		except KeyboardInterrupt:
			quit()
		except Exception as e:
			print(e)
			print("Failed to parse")
			pass

			



