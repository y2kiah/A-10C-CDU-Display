# Raspberry Pi CDU screen

These instructions will help you configure a Raspberry Pi to behave like an A-10C CDU screen, interfaced with DCS-BIOS. The Pi will auto-login and run the CDU program on boot, so powering it on for a flight is a seamless experience for the home cockpit builder.

The CDU display outputs text to the Linux terminal using the curses library, it is not graphical. The processing requirements are very low and the program can be run, developed and debugged over SSH. Some of the configuration steps below involve Linux shell setup to get a 16x32 line output on the CDU screen, and change the terminal font, which turns out to work perfectly for the CDU. There are two missing characters that have unique and appropriate stand-ins in this program. A more complicated graphical program would address that, but the simplicity of this script combined with the ability to run and debug it remotely (with a headless setup) are well worth the trade-off IMO.

The Linux terminal emulator `screen` is used to run `cdu.py` on boot, so it is possible to SSH into the Pi, and attach to the on-screen session using `screen -x`.

CDU buttons and back lighting are also implemented in the same `cdu.py` script as the display. The key pad is assumed to be a matrix, and can be easily reconfigured to match the actual physical matrix of your PCB.

## Setup Instructions

1) get a "Raspberry Pi 4.0 inch HDMI LCD GPIO Touch"
	http://spotpear.com/index.php/spotpear-raspberry-pi-lcd/raspberry-pi-lcd-4-inch-hdmi-lcd-gpio-touch

2) install LCD drivers:
	http://spotpear.com/learn/EN/raspberry-pi/Raspberry-Pi-LCD/Drive-the-LCD.html

3) in `raspi-config` set option for auto-login on boot with pi user

4) set default terminal font with `sudo dpkg-reconfigure -plow console-setup` to `UTF8, guess, TerminusBold, 16x32`

5) set up python3 and screen
	```Shell
    sudo apt-get install python3-setuptools & easy_install3 pip
	pip install paho-mqtt
	sudo apt-get install screen
	sudo apt-get install python3-smbus
	sudo apt-get install python-rpi.gpio python3-rpi.gpio
    ```

6) add to `.profile`
	```Shell
	# start screen session running cdu program  when not an ssh session
	if [ ! -n "$SSH_CLIENT" ] && [ ! -n "$SSH_TTY" ]; then
			screen -t cdu bash -c "python3 ~/CDUscreen/cdu.py; exec bash"
	fi
	```
7) add `.screenrc`
	```Shell
	startup_message off
	vbell off
	bell_msg ""
	```

8) install pi-blaster-mqtt
	- clone the git repo
		`git clone git@github.com:y2kiah/pi-blaster-mqtt.git`
	- (optional) edit mqtt-client.c, set localhost to the IP of your mqtt server
	- follow install instructions on https://github.com/gherlein/pi-blaster-mqtt
	- before executing `sudo make install`, create the following environment file
	- create environment file for pi-blaster service, configure control of only pin 22
		`sudo su -c 'echo "DAEMON_OPTS=\"--gpio=22\"" > /etc/default/pi-blaster-mqtt'`

9) allow pi to shut down without password (enables the shutdown menu option)
	- open the sudoers file with `sudo vim /etc/sudoers`, add the following to the end
		```Shell
		# allow pi user to shut down with no password
		nobody ALL = NOPASSWD: /sbin/shutdown*
		```
	- use `:x!` to save

10) install MQTT and mosquitto (use an online tutorial)
	- can be run on same or a separate Pi
	- only one MQTT server needed for whole cockpit

11) install NodeRED and deploy DCS-BIOS-Node project
	- available in a separate project
	- recommend running on a separate Raspberry Pi 3 B+
	- only one NodeRED instance needed for whole cockpit

12) (optional) enable export of CDU in HUD-only view

	in `Mods\aircraft\A-10C\Cockpit\Scripts\CDU\indicator\CDU_init.lua` add to top

	```Lua
	dofile(LockOn_Options.common_script_path.."devices_defs.lua")
	dofile(LockOn_Options.common_script_path.."ViewportHandling.lua")	--added for Instrument Export Mod

	indicator_type = indicator_types.COMMON

	--added for Instrument Export Mod
	purposes                  = {render_purpose.GENERAL}
	update_screenspace_diplacement(1,0,0)    
	try_find_assigned_viewport("ED_A10C_CDU","CDU_SCREEN")
	--end Instrument Export Mod adds
	```
		
	add in `Config\MonitorSetup\[custom monitor].lua`
	
	```Lua
	ED_A10C_CDU =
	{
		x = -1;
		y = 0;
		width = 1;
		height = 1;
	}
	```

13) (optional, not CDU specific) remove MFCD from HUD-only view

	in `Mods\aircraft\A-10C\Cockpit\Scripts\MFCD\indicator\MFCD_init.lua` remove from "purposes" arrays
	
	```render_purpose.HUD_ONLY_VIEW```

