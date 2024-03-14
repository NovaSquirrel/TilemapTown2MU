#!/usr/bin/env python
# https://www.moo.mud.org/mcp/
# https://wiki.mudlet.org/w/Standards:MUD_Client_Media_Protocol
import asyncio, sys, weakref, signal

# Set up an event loop first
from twisted.internet import asyncioreactor
event_loop = asyncio.SelectorEventLoop()
asyncioreactor.install(event_loop)

# Set up other stuff
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
from twisted.internet import task
from twisted.internet import reactor
from town import *
from shared import *

connect_message = [
"  _______ _ _                              _______                  ",
" |__   __(_) |                            |__   __|                 ",
"    | |   _| | ___ _ __ ___   __ _ _ __      | | _____      ___ __  ",
"    | |  | | |/ _ \\ '_ ` _ \\ / _` | '_ \\     | |/ _ \\ \\ /\\ / / '_ \\ ",
"    | |  | | |  __/ | | | | | (_| | |_) |    | | (_) \\ V  V /| | | |",
"    |_|  |_|_|\\___|_| |_| |_|\\__,_| .__/     |_|\\___/ \\_/\\_/ |_| |_|",
"                                  | |                               ",
"                                  |_|     Tilemap Town MU* Gateway! ",
"  https://github.com/NovaSquirrel/TilemapTown2MU",
"  https://novasquirrel.com/town/",
" ----------------------------------------------",
"  'connect <character> <password>' to connect",
"  'connect guest guest' to connect as a guest",
"  QUIT to disconnect"
]
#tilemap_town_uri = 'ws://localhost:12550'
tilemap_town_uri = 'wss://novasquirrel.com/townws/'

# ---------------------------------------------------------

def separate_first_word(text, lowercase_first=True):
	space = text.find(" ")
	command = text
	arg = ""
	if space >= 0:
		command = text[0:space]
		arg = text[space+1:]
	if lowercase_first:
		command = command.lower()
	return (command, arg)

# ---------------------------------------------------------

class MUConnection(LineReceiver): # Handles a single user's connection
	def __init__(self):
		self.line_handler = self.pre_connect_state_handler
		self.idle_time = 0
		self.tilemap_town = None
		self.color_enabled = True
		self.rgb_color_enabled = True
		self.utf8_enabled = True

	# Handles string->bytes conversion for sendLine
	def sendLineAsBytes(self, text):
		# uncomment the next two lines and the Timer import and comment out the normal sendline to introduce 1s of latency to all messages for lag testing
		#t = Timer(1, self.sendLine, args=[text.encode('utf-8')])
		#t.start()
		self.sendLine(text.encode('utf-8'))

	def sendLinesAsBytes(self, lines):
		for line in lines:
			self.sendLine(line.encode('utf-8'))

	# .----------------------------------------------------
	# | Callbacks
	# '----------------------------------------------------

	def connectionMade(self):
		self.transport.setTcpNoDelay(True)
		self.ip = self.transport.getPeer().host
		self.sendLinesAsBytes(connect_message)
		print("Connection from " + self.ip)

	def connectionLost(self, reason):
		print("Client disconnected: %s" % reason)
		if self.tilemap_town and self.tilemap_town.websocket:
			asyncio.ensure_future(self.tilemap_town.websocket.close(), loop=event_loop)
			
	def lineReceived(self, line):
		self.idle_time = 0
		try:
			self.line_handler(line.decode('utf-8'))
		except:
			exception_type = sys.exc_info()[0]
			print("Exception: %s" % exception_type.__name__)
			self.sendLineAsBytes("Error: Exception (%s)" % exception_type.__name__)
			raise

	# .----------------------------------------------------
	# | Utilities
	# '----------------------------------------------------

	def disconnect(self, reason):
		if reason != None:
			self.sendLineAsBytes(reason)
		self.transport.loseConnection()

	def send_to_town(self, command, params):
		if self.tilemap_town:
			self.tilemap_town.send_command(command, params)

	# .----------------------------------------------------
	# | States
	# '----------------------------------------------------

	def pre_connect_state_handler(self, text):
		command, arg = separate_first_word(text)
		if command == "connect": # connect username password
			username, password = separate_first_word(arg)
			self.tilemap_town = TilemapTown(self)
			self.line_handler = self.connecting_state_handler
			asyncio.ensure_future(self.tilemap_town.run_client(tilemap_town_uri, username, password), loop=event_loop)
			self.sendLineAsBytes("Connecting to Tilemap Town...")
		elif command == "nocolor":
			self.color_enabled = False
		elif command == "8color":
			self.rgb_color_enabled = False
		elif command == "ascii":
			self.utf8_enabled = False
		elif command == "test":
			self.sendLineAsBytes("Test")
		elif command == "quit":
			self.disconnect("Goodbye!")

	def connecting_state_handler(self, text):
		if text == "quit":
			self.disconnect("Goodbye!")

	def connected_state_handler(self, text):
		# Look for a prefix like " or :
		for k, v in prefix_gateway_command_handlers.items():
			if text.startswith(k):
				v(self, text[len(k):])
				return

		# Otherwise it's a normal command
		command, arg = separate_first_word(text)
		if command in command_aliases:
			command = command_aliases[command]
		if command in pass_through_commands:
			self.send_to_town("CMD", {"text": text})
		elif command in gateway_command_handlers:
			gateway_command_handlers[command](self, arg)
		else:
			self.sendLineAsBytes("Error: Unknown gateway command: %s" % command)


	# .----------------------------------------------------
	# | Formatting
	# '----------------------------------------------------

	def ansi_fg(self, color):
		if not self.color_enabled:
			return ""
		return "\x1b[%dm" % (color.value + 30)

	def ansi_bg(self, color):
		if not self.color_enabled:
			return ""
		return "\x1b[%dm" % (color.value + 40)

	def ansi_fg8(self, rgb):
		if not self.color_enabled:
			return ""
		return "\x1b[38;2;%d;%d;%dm" % rgb_from_hex(rgb)

	def ansi_bg8(self, rgb):
		if not self.color_enabled:
			return ""
		return "\x1b[48;2;%d;%d;%dm" % rgb_from_hex(rgb)

	def ansi_reset(self):
		if not self.color_enabled:
			return ""
		return "\x1b[0m"

# ---------------------------------------------------------

class MUFactory(Factory):
	def __init__(self):
		self.users = weakref.WeakSet()
		signal.signal(signal.SIGINT, self.signal_handler)

	def buildProtocol(self, addr):
		connection = MUConnection()
		self.users.add(connection)
		return connection
	
	def signal_handler(self, sig, frame):
		# Let everyone know they were disconnected for maintenance
		for user in self.users:
			user.disconnect("Gateway server shutting down")
		reactor.stop()

def check_on_timeouts():
	for user in factory.users:
		user.idle_time += 1

# .----------------------------------------------
# | Command registration
# '----------------------------------------------

# Commands where the first word needs to be a command name
gateway_command_handlers = {}
# Commands where the character (or several characters) needs to match
prefix_gateway_command_handlers = {}
# Commands that will be sent to the server as a CMD message as-is
pass_through_commands = {'tell', 'roll', 'away', 'status', 'nick', 'userdesc', 'userpic', 'login', 'register', 'changepass', 'who', 'entitywho', 'gwho', 'look', 'last', 'goback', 'tpa', 'tpahere', 'tpaccept', 'tpdeny', 'tpcancel', 'sethome', 'home', 'carry', 'followme', 'hopon', 'hopoff', 'dropoff', 'rideend', 'carrywho', 'ridewho', 'giveitem', 'publicmaps', 'publicmaps', 'mapid', 'map', 'time', 'listeners', 'entity', 'e', 'msg', 'stat', 'findrp', 'findiic', 'tpi', 'whereare', 'wa', 'ewho', 'whoami', 'p', 'topic', 'cleartopic'}
# Commands that are alternate names for other commands
command_aliases = {}

def gateway_command(prefix=None, command=None, aliases=[]):
	def decorator(f):
		if prefix != None:
			prefix_gateway_command_handlers[prefix] = f
		if command != None:
			command_name = command
		else:
			command_name = f.__name__[3:]
		for alias in aliases:
			command_aliases[alias] = command_name
		gateway_command_handlers[command_name] = f
	return decorator

# .----------------------------------------------
# | Gateway commands
# '----------------------------------------------

@gateway_command()
def fn_echo(self, arg):
	self.sendLineAsBytes(arg)

@gateway_command(prefix='"')
def fn_say(self, arg):
	self.send_to_town("MSG", {"text": arg})

@gateway_command(prefix=':')
def fn_pose(self, arg):
	self.send_to_town("MSG", {"text": "/me "+arg})

@gateway_command()
def fn_spoof(self, arg):
	self.send_to_town("MSG", {"text": "/spoof "+arg})

@gateway_command(prefix='/')
def fn_cmd(self, arg):
	if arg.startswith("me ") or arg.startswith("spoof ") or arg.startswith("ooc "):
		self.send_to_town("MSG", {"text": "/"+arg})
	else:
		self.send_to_town("CMD", {"text": arg})

@gateway_command()
def fn_allcommands(self, arg):
	self.sendLineAsBytes(" ".join(gateway_command_handlers.keys()))

@gateway_command()
def fn_quit(self, arg):
	self.disconnect("Goodbye!")

def try_edge_link(self, link):
	if self.tilemap_town and self.tilemap_town.map_info:
		info = self.tilemap_town.map_info
		if "edge_links" in info:
			if info["edge_links"][link]:
				self.send_to_town("CMD", {"text": "map %s" % info["edge_links"][link]})
			else:
				self.sendLineAsBytes("That map isn't connected in that direction")
		else:
			self.sendLineAsBytes("That map isn't connected to other maps")

@gateway_command()
def fn_east(self, arg):
	try_edge_link(self, 0)
@gateway_command()
def fn_southeast(self, arg):
	try_edge_link(self, 1)
@gateway_command()
def fn_south(self, arg):
	try_edge_link(self, 2)
@gateway_command()
def fn_southwest(self, arg):
	try_edge_link(self, 3)
@gateway_command()
def fn_west(self, arg):
	try_edge_link(self, 4)
@gateway_command()
def fn_northwest(self, arg):
	try_edge_link(self, 5)
@gateway_command()
def fn_north(self, arg):
	try_edge_link(self, 6)
@gateway_command()
def fn_northeast(self, arg):
	try_edge_link(self, 7)

@gateway_command()
def fn_show(self, arg):
	if self.tilemap_town:
		me = self.tilemap_town.who.get(self.tilemap_town.entity_id, None)
		if me != None:
			self.tilemap_town.print_map_rect_around_xy(me['x'], me['y'], 40, 15)

@gateway_command()
def fn_bigshow(self, arg):
	if self.tilemap_town:
		me = self.tilemap_town.who.get(self.tilemap_town.entity_id, None)
		if me != None:
			self.tilemap_town.print_map_rect_around_xy(me['x'], me['y'], 70, 30)

def my_coords(self):
	if self.tilemap_town == None:
		return None
	me = self.tilemap_town.who.get(self.tilemap_town.entity_id, None)
	if me == None:
		return None
	return (me["x"], me["y"])

def is_within_map(self, x, y):
	if not self.tilemap_town:
		return False
	if x < 0 or x >= self.tilemap_town.map_width or y < 0 or y >= self.tilemap_town.map_height:
		return False
	return True

def get_coords_offset(self, arg, command):
	if arg == "w":
		arg = "0 -1"
	elif arg == "a":
		arg = "-1 0"
	elif arg == "s":
		arg = "0 1"
	elif arg == "d":
		arg = "1 0"
	elif arg == "":
		arg = "0 0"
	s = arg.split(' ')
	if len(s) != 2:
		self.sendLineAsBytes("Syntax: %s x y" % command)
		return None
	here = my_coords(self)
	if here == None:
		return None
	try:
		try_x = here[0] + int(s[0])
		try_y = here[1] + int(s[1])
	except:
		self.sendLineAsBytes("Syntax: %s x y" % command)
		return None

	if not is_within_map(self, try_x, try_y):
		self.sendLineAsBytes("Error: %d,%d not within map" % (try_x, try_y))
		return None
	return (try_x, try_y)

@gateway_command(command='?turf', aliases=["?t"])
def fn_checkturf(self, arg):
	coords = get_coords_offset(self, arg, "?turf")
	if coords == None:
		return
	turf = self.tilemap_town.map_turfs[coords[0]][coords[1]]
	if turf == None:
		self.sendLineAsBytes("There's no turf there")
		return
	turf = self.tilemap_town.lookup_atom(turf)
	self.sendLineAsBytes("At %d,%d is \"%s\"" % (coords[0], coords[1], turf.get("name", "???")))

@gateway_command(command='?obj', aliases=["?o"])
def fn_checkobj(self, arg):
	coords = get_coords_offset(self, arg, "?obj")
	if coords == None:
		return
	objs = self.tilemap_town.map_objs[coords[0]][coords[1]]
	if objs == None:
		self.sendLineAsBytes("There's no obj there")
		return
	names = []
	for o in objs:
		o = self.tilemap_town.lookup_atom(o)
		names.append(o.get("name", "???"))
	self.sendLineAsBytes("At %d,%d is \"%s\"" % (coords[0], coords[1], ", ".join(names)))

@gateway_command(command=".")
def fn_move(self, arg):
	if self.tilemap_town == None:
		return
	me = self.tilemap_town.who.get(self.tilemap_town.entity_id, None)
	if me == None:
		return
	if arg == "":
		self.tilemap_town.print_map_rect_around_xy(me['x'], me['y'], 20, 9)
		return
	old_x = me["x"]
	old_y = me["y"]
	bumped = False

	def bump():
		nonlocal me, try_x, try_y, old_x, old_y, save_x, save_y, bumped
		if bumped:
			return
		bumped = True
		params = {"bump": [try_x, try_y], "if_map": self.tilemap_town.map_id, "dir": new_direction}
		if old_x != save_x or old_y != save_y:
			params["from"] = [old_x, old_y]
			params["to"] = [save_x, save_y]
			me["x"] = save_x
			me["y"] = save_y
			try_x = save_x
			try_y = save_y
		self.tilemap_town.send_command("MOV", params)

	new_direction = None
	try_x = old_x
	try_y = old_y
	for char in arg:
		save_x = try_x
		save_y = try_y
		if char == 'w':
			new_direction = 6
			try_y -= 1
		elif char == 'a':
			new_direction = 4
			try_x -= 1
		elif char == 's':
			new_direction = 2
			try_y += 1
		elif char == 'd':
			new_direction = 0
			try_x += 1

		if not is_within_map(self, try_x, try_y):
			bump()
			return

		obj = (self.tilemap_town.map_objs[try_x][try_y])
		if isinstance(obj, list):
			had_sign = False
			for o in obj:
				o = self.tilemap_town.lookup_atom(o)
				if o.get("density", False):
					bump()
					if o.get("type", None) == "sign":
						name = o.get("name", None)
						if name == "sign":
							self.sendLineAsBytes("The sign says: %s" % o.get("message", "Nothing?"))
						else:
							self.sendLineAsBytes("The sign (\"%s\") says: %s" % (name, o.get("message", "Nothing?")))
						had_sign = True
			if bumped:
				if not had_sign:
					self.sendLineAsBytes("Bump!")
				break

		turf = self.tilemap_town.lookup_atom(self.tilemap_town.map_turfs[try_x][try_y])
		if turf != None and turf.get("density", False):
			self.sendLineAsBytes("Bump!")
			bump()
			break
				
	if not bumped:
		me["x"] = try_x
		me["y"] = try_y
		self.tilemap_town.send_command("MOV", {"from": [old_x, old_y], "to": [try_x, try_y], "dir": new_direction})
	if me['x'] != old_x or me['y'] != old_y:
		self.tilemap_town.print_map_rect_around_xy(me['x'], me['y'], 20, 9)

# .----------------------------------------------
# | Server setup
# '----------------------------------------------

print("Ready for clients")
factory = MUFactory()
reactor.listenTCP(4201, factory)
reactor.listenTCP(4201, factory, interface="::")
l = task.LoopingCall(check_on_timeouts)
l.start(30) # Every 30 seconds
reactor.run()
