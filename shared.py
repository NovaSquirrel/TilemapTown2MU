from enum import Enum

# .----------------------------------------------------
# | Formatting
# '----------------------------------------------------

class BasicColor(Enum):
	BLACK = 0
	RED = 1
	GREEN = 2
	YELLOW = 3
	BLUE = 4
	MAGENTA = 5
	CYAN = 6
	WHITE = 7

def rgb_from_hex(hex):
	return (int(hex[0:2], 16), int(hex[2:4], 16), int(hex[4:6], 16))

def ansi_fg(color):
	return "\x1b[%dm" % (color.value + 30)

def ansi_bg(color):
	return "\x1b[%dm" % (color.value + 40)

def ansi_fg8(r, g, b):
	return "\x1b[38;2;%d;%d;%dm" % (r,g,b)

def ansi_bg8(r, g, b):
	return "\x1b[48;2;%d;%d;%dm" % (r,g,b)

def ansi_fg_hex(rgb):
	return "\x1b[38;2;%d;%d;%dm" % rgb_from_hex(rgb)

def ansi_bg_hex(rgb):
	return "\x1b[48;2;%d;%d;%dm" % rgb_from_hex(rgb)

def ansi_reset():
	return "\x1b[0m"

LIGHT_SHADE      = "░"
MEDIUM_SHADE     = "▒"
DARK_SHADE       = "▓"
FULL_BLOCK       = "█"
LEFT_HALF_BLOCK  = "▌"
RIGHT_HALF_BLOCK = "▐"
LOWER_HALF_BLOCK = "▄"
UPPER_HALF_BLOCK = "▀"
BLACK_SQUARE     = "■"
WHITE_SMILE      = "☺"
BLACK_SMILE      = "☻"
HEART_SUIT       = "♥" # Seems to render as an emoji
DIAMOND_SUIT     = "♦"
CLUB_SUIT        = "♣"
SPADE_SUIT       = "♠"
BULLET           = "•"
INVERSE_BULLET   = "◘"
WHITE_CIRCLE     = "○"
INVERSE_WHITE_CIRCLE = "◙"
TRIANGLE_UP      = "▲"
TRIANGLE_DOWN    = "▼"
TRIANGLE_LEFT    = "◄"
TRIANGLE_RIGHT   = "►"
BLACK_RECTANGLE  = "▬"
MUSIC_NOTE       = "♪"
MUSIC_NOTES      = "♫"
BOX_DRAWING_INNER= "╬"
