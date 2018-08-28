import curses

# greens
#2
#10
#22
#28
#34
#40
#46

def main(stdscr):
	curses.start_color()
	curses.use_default_colors()

	stdscr.addstr("can change " if curses.can_change_color() else "cannot change ")
	stdscr.addstr(str(curses.COLORS))

	for i in range(0, curses.COLORS):
		curses.init_pair(i + 1, i, -1)
	try:
		for i in range(0, 256):
			stdscr.addstr(str(i), curses.color_pair(i))
	except curses.ERR:
		# End of screen reached
		pass

	stdscr.getch()

curses.wrapper(main)
