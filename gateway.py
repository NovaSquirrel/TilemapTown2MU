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
		if command in gateway_command_handlers:
			gateway_command_handlers[command](self, arg)
		else:
			self.sendLineAsBytes("Error: Unknown gateway command: %s" % command)

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

gateway_command_handlers = {}
prefix_gateway_command_handlers = {}

def gateway_command(prefix=None):
	def decorator(f):
		if prefix != None:
			prefix_gateway_command_handlers[prefix] = f
		command_name = f.__name__[3:]
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
