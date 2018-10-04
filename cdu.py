#!/usr/bin/env python3

from __future__ import print_function
import sys
import curses
import paho.mqtt.client as mqtt
from curses import wrapper
import smbus
import time
import RPi.GPIO as GPIO

mqtt_host = "192.168.0.174"
mqtt_port = 1883

# these are BCM numbers
pwm_gpio_bcm = 25  # corresponds to pin #22
row9_gpio_bcm = 15 # corresponds to pin #10

max_rows = 10
max_cols = 24
start_y = 0
start_x = 4

Disconnected = 0
Connected = 1
Sim = 2

mode = Disconnected
lines = [(" "*max_cols) for r in range(max_rows)]

brt_green = 1
dim_green = 2
active_color = brt_green

DEVICE = 0x20 # Device address (A0-A2)
IODIRA = 0x00 # Pin direction register port A
IODIRB = 0x01 # Pin direction register port B
OLATA  = 0x14 # Register for outputs port A
OLATB  = 0x15 # Register for outputs port B
GPIOA  = 0x12 # Register for inputs port A
GPIOB  = 0x13 # Register for inputs port B

key_states = [0 for r in range(72)]
key_changes = []

# keys laid out exactly as they are wired into rows and columns
key_matrix = [
	None,        None,        None,           None,            ["cdu_pg",0,1],"cdu_mk",    ["cdu_scroll",0,1],None,
	"cdu_spc",   "cdu_y",     "cdu_z",        ["cdu_data",2,1],["cdu_pg",2,1],"cdu_na1",   "cdu_na2",         "cdu_bck",
	"cdu_t",     "cdu_u",     "cdu_v",        "cdu_w",         "cdu_point",   "cdu_0",     "cdu_slash",       "cdu_s",
	"cdu_lsk_3r","cdu_lsk_5r","cdu_lsk_7r",   "cdu_lsk_9r",    "cdu_lsk_9l",  "cdu_lsk_7l","cdu_lsk_5l",      "cdu_lsk_3l",
	"cdu_fpm",   "cdu_prev",  ["cdu_brt",0,1],["cdu_brt",2,1], "cdu_sys",     "cdu_nav",   "cdu_wp",          "cdu_oset",
	"cdu_b",     "cdu_c",     "cdu_d",        "cdu_e",         "cdu_1",       "cdu_2",     "cdu_3",           "cdu_a",
	"cdu_h",     "cdu_i",     "cdu_j",        "cdu_k",         "cdu_4",       "cdu_5",     "cdu_6",           "cdu_g",
	"cdu_n",     "cdu_o",     "cdu_p",        "cdu_q",         "cdu_7",       "cdu_8",     "cdu_9",           "cdu_m",
	"cdu_r",     "cdu_l",     "cdu_f",        ["cdu_data",0,1],"cdu_fa",      "cdu_clr",   ["cdu_scroll",2,1],"cdu_x"
]


def eprint(*args, **kwargs):
	print(*args, file=sys.stderr, **kwargs)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
	global mode
	win = userdata['win']
	win.clear()
	win.addnstr(4, 0, ("Connected to MQTT (" + str(rc) + ")").center(max_cols,' '), max_cols)
	win.addnstr(5, 0, "Waiting for telemetry...".center(max_cols,' '), max_cols)
	win.noutrefresh()
	curses.doupdate()

	mode = Connected

	# Subscribing in on_connect() means that if we lose the connection and
	# reconnect then subscriptions will be renewed.

	# subscribe to cdu_display messages with single-level wildcard
	# example: dcs-bios/output/cdu_display/cdu_line0
	client.subscribe("dcs-bios/output/cdu_display/+")
	client.subscribe("dcs-bios/output/cdu/cdu_brt")
	client.subscribe("dcs-bios/output/lcp/lcp_aux_inst")


def on_disconnect(client, userdata, rc):
	global mode
	mode = Disconnected
	win = userdata['win']
	win.addnstr(4, 0, "Connecting to MQTT at".center(max_cols,' '), max_cols)
	win.addnstr(5, 0, (mqtt_host + ":" + str(mqtt_port)).center(max_cols,' '), max_cols)
	win.refresh()


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
	global mode
	global lines
	global active_color
	win = userdata['win']

	if mode == Connected:
		mode = Sim
		win.clear()

	if msg.topic.find("cdu_line") != -1:
		row = int(msg.topic[-1])

		payload = (msg.payload
			.replace(b"\xB6", bytes("\u2588","utf-8"))  # cursor block
			.replace(b"\xBB", bytes("\u2192","utf-8"))  # arrow right
			.replace(b"\xAB", bytes("\u2190","utf-8"))  # arrow left
			.replace(b"\xA1", bytes("\u2591","utf-8"))  # [] data entry
			.replace(b"\xA9", bytes("\u2022","utf-8"))  # bullseye
			.replace(b"\xB1", bytes("\u00B1","utf-8"))  # +/-
			.replace(b"\xAE", bytes("\u2195","utf-8"))  # up/down arrow
			.replace(b"\xB0", bytes("\u00B0","utf-8"))) # degree

		try:
			line = payload.decode("utf-8")
			lines[row] = line
			win.addnstr(row, 0, line, max_cols, curses.color_pair(active_color))
		except:
			pass

	elif msg.topic.find("cdu_brt") != -1:
                if int(msg.payload) == 0:
                        active_color = dim_green
                        redraw_lines(win)
                elif int(msg.payload) == 2:
                        active_color = brt_green
                        redraw_lines(win)

	elif msg.topic.find("lcp_aux_inst") != -1:
		aux_light = int(msg.payload) / 65535
		client.publish("pi-blaster-mqtt/text", "{0}={1:.2f}".format(pwm_gpio_bcm, aux_light))

	win.noutrefresh()
	curses.doupdate()


def redraw_lines(win):
	for row in range(max_rows):
		try:
			win.addnstr(row, 0, lines[row], max_cols, curses.color_pair(active_color))
		except:
			pass


# set up i2c bus for reading key matrix from MCP23017
def init_MCP23017():
	bus = smbus.SMBus(1) # Rev 2 Pi uses i2c bus 1

	# Set all GPA pins as outputs by setting all bits of IODIRA register to 0
	bus.write_byte_data(DEVICE, IODIRA, 0x00)
	# Set all 8 output bits to 0
	bus.write_byte_data(DEVICE, OLATA, 0)

	return bus


def init_GPIO():
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(row9_gpio_bcm, GPIO.IN, pull_up_down = GPIO.PUD_DOWN)


def main(stdscr):
	global key_states
	global key_changes

	curses.start_color()
	curses.use_default_colors()
	win = curses.newwin(max_rows, max_cols, start_y, start_x)

	client = mqtt.Client()
	client.on_connect = on_connect
	client.on_disconnect = on_disconnect
	client.on_message = on_message
	client.user_data_set({
		'win': win,
		'stdscr': stdscr
	})

	stdscr.clear()
	stdscr.refresh()
	curses.curs_set(0)
	curses.init_pair(brt_green, 10, curses.COLOR_BLACK)
	curses.init_pair(dim_green, 22, curses.COLOR_BLACK)
	curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)

	win.addnstr(4, 0, "Connecting to MQTT at".center(max_cols,' '), max_cols)
	win.addnstr(5, 0, (mqtt_host + ":" + str(mqtt_port)).center(max_cols,' '), max_cols)
	win.refresh()

	client.connect(mqtt_host, mqtt_port, 60)

	bus = init_MCP23017()

	init_GPIO()

	# dispatches callbacks and handles reconnecting.
	client.loop_start()

	# use CTRL-C to quit
	running = True
	while running:
		for col in range(8):
			out_mask = 1 << col
			# columns are on port A
			bus.write_byte_data(DEVICE, OLATA, out_mask)
			time.sleep(0.001)
			# rows are on port B
			in_byte = bus.read_byte_data(DEVICE, GPIOB)

			for row in range(9):
				key_down = 0
				if (row < 8):
					key_down = (in_byte >> row) & 0x01
				else: # row 9
					key_down = GPIO.input(row9_gpio_bcm)

				k = row * 8 + col
				if key_states[k] != key_down:
					key = key_matrix[k]
					key_val = key_down
					if isinstance(key, str):
						key_str = key
					# if not a string or None, it's an array [name, down val, up val]
					elif key is not None:
						key_str = key[0]
						key_val = key[1] if key_val == 1 else key[2]

					key_changes.append([key_str,key_val])

				key_states[k] = key_down

		for key_change in key_changes:
			client.publish("dcs-bios/input/cdu/"+key_change[0], key_change[1])

		key_changes.clear()

		# this section prints the key matrix
		if False:
			win.clear() #temp
			for k in range(72):
				r = k // 8
				c = k % 8
				win.addnstr(r, c, str(key_states[k]), max_cols)
			win.noutrefresh()
			curses.doupdate()

	client.disconnect()
	client.loop_stop()
	GPIO.cleanup()

wrapper(main)
