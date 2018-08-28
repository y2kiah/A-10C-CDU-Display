from __future__ import print_function
import sys
import curses
import paho.mqtt.client as mqtt
from curses import wrapper

mqtt_host = "192.168.0.174"
mqtt_port = 1883

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


def on_disconnect(client, userdata, rc):
	global mode
	mode = Disconnected
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

	win.noutrefresh()
	curses.doupdate()


def redraw_lines(win):
	for row in range(max_rows):
		try:
			win.addnstr(row, 0, lines[row], max_cols, curses.color_pair(active_color))
		except:
			pass


def main(stdscr):
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
	curses.init_pair(dim_green, 22,  curses.COLOR_BLACK)
	curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)

	win.addnstr(4, 0, "Connecting to MQTT at".center(max_cols,' '), max_cols)
	win.addnstr(5, 0, (mqtt_host + ":" + str(mqtt_port)).center(max_cols,' '), max_cols)
	win.refresh()

	client.connect(mqtt_host, mqtt_port, 60)

	# Blocking call that processes network traffic, dispatches callbacks and handles reconnecting.
	client.loop_forever()


wrapper(main)
