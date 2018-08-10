import curses
import paho.mqtt.client as mqtt
from curses import wrapper

max_rows = 10
max_cols = 24
start_y = 0
start_x = 4

Disconnected = 0
Connected = 1
Sim = 2

mode = Disconnected


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
	global mode
	win = userdata['win']
	win.clear()
	win.addnstr(4, 0, ("Connected, result code " + str(rc)).center(max_cols,' '), max_cols)
	win.addnstr(5, 0, "Waiting for telemetry...".center(max_cols,' '), max_cols)
	win.noutrefresh()
	curses.doupdate()

	mode = Connected

	# Subscribing in on_connect() means that if we lose the connection and
	# reconnect then subscriptions will be renewed.

	# subscribe to cdu_display messages with single-level wildcard
	# example: dcs-bios/output/cdu_display/cdu_line0
	client.subscribe("dcs-bios/output/cdu_display/+")


def on_disconnect(client, userdata, rc):
	global mode
	mode = Disconnected
	win.addnstr(4, 0, "MQTT at localhost:1883".center(max_cols,' '), max_cols)
	win.addnstr(5, 0, "Connecting...".center(max_cols,' '), max_cols)
	win.refresh()


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
	global mode
	win = userdata['win']

	if mode == Connected:
		mode = Sim
		win.clear()

	if msg.topic.find("cdu_line"):
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
			win.addnstr(row, 0, line, max_cols, curses.color_pair(1))
		except:
			pass

	win.noutrefresh()
	curses.doupdate()
		

def main(stdscr):
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
	curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
	curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)

	win.addnstr(4, 0, "MQTT at localhost:1883".center(max_cols,' '), max_cols)
	win.addnstr(5, 0, "Connecting...".center(max_cols,' '), max_cols)
	win.refresh()

	client.connect("localhost", 1883, 60)

	# Blocking call that processes network traffic, dispatches callbacks and handles reconnecting.
	client.loop_forever()


#s = ""
#for x in range(32, 12288):
#	s = s + chr(x)
#print(s)

wrapper(main)
