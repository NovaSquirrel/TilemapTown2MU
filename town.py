# Tilemap Town connection
from shared import *
import asyncio, json, websockets

# .----------------------------------------------
# | Tilemap Town class
# '----------------------------------------------

class TilemapTown(object):
	def __init__(self, connection):
		self.entity_id = None
		self.websocket = None
		self.mu_connection = connection

		# State
		self.entity_id = None
		self.map_id = None
		self.map_info = {}
		self.who = {}

	# .----------------------------------------------
	# | Websocket connection
	# '----------------------------------------------

	async def run_client(self, uri, username, password):
		print("Connecting")

		async with websockets.connect(uri=uri, extra_headers={'X-Real-IP': 'testing'}) as self.websocket:
			try:
				idn_info = {
					#"name": "Gateway test",
					"client_name": "TilemaptTown2MU",
					"features": {
						"batch": {"version": "0.0.1"}
					}
				}
				if username != None and username != 'guest':
					idn_info["username"] = username
					idn_info["password"] = password
				self.send_command("IDN", idn_info)
				async for message in self.websocket:
					# Split the message into parts
					if len(message)<3:
						continue
					if message[0:4] == "BAT ":
						for sub_message in message[4:].splitlines():
							self.receive_server_message(sub_message)
					else:
						self.receive_server_message(message)

			except websockets.ConnectionClosed:
				print("Connection closed")
		self.mu_connection.line_handler = self.mu_connection.pre_connect_state_handler

	def receive_server_message(self, message):
		print("<< "+message)
		message_type = message[0:3]
		arg = {}
		if len(message) > 4:
			arg = json.loads(message[4:])
		if message_type in protocol_handlers:
			protocol_handlers[message_type](self, arg)

	def send_command(self, command, params):
		print(">> "+command+ " " + (json.dumps(params) if params != None else ""))
		if self.websocket == None:
			return
		def make_protocol_message_string(command, params):
			if params != None:
				return command + " " + json.dumps(params)
			return command
		asyncio.ensure_future(self.websocket.send(make_protocol_message_string(command, params)))

	def send_cmd_command(self, command):
		self.send_command("CMD", {"text": command})

	def print_line(self, text):
		self.mu_connection.sendLineAsBytes(text)

	def print_lines(self, text):
		self.mu_connection.sendLinesAsBytes(text)

# -----------------------------------------------------------------------------

# .----------------------------------------------
# | Command registration
# '----------------------------------------------

protocol_handlers = {}
def protocol_command():
	def decorator(f):
		command_name = f.__name__[3:]
		protocol_handlers[command_name] = f
	return decorator

# .----------------------------------------------
# | Protocol message handlers
# '----------------------------------------------

@protocol_command()
def fn_PIN(self, arg):
	self.send_command("PIN", None)

@protocol_command()
def fn_ERR(self, arg):
	self.print_line("Error: " + arg["text"])

@protocol_command()
def fn_CMD(self, arg):
	self.print_line(">> " + arg["text"])

@protocol_command()
def fn_MSG(self, arg):
	if "name" in arg:
		lowercase = arg["text"].lower()
		if lowercase.startswith("/me "):
			self.print_line("* %s %s" % (arg["name"], arg["text"][4:]))
		elif lowercase.startswith("/ooc "):
			self.print_line("[OOC] %s: %s" % (arg["name"], arg["text"][5:]))
		elif lowercase.startswith("/spoof "):
			self.print_line("* %s (by %s)" % (arg["text"][7:], arg["name"]))
		else:
			self.print_line("<%s> %s" % (arg["name"], arg["text"]))
	else:
		self.print_line("Server message: %s" % arg["text"])
		if "buttons" in arg:
			self.print_line("[Buttons]")
			for i in range(len(arg["buttons"]) // 2):
				option  = arg["buttons"][i*2]
				command = arg["buttons"][i*2+1]
				self.print_line("| %s: %s" % (option, command))

@protocol_command()
def fn_PRI(self, arg):
	text = arg["text"]
	lower = text.lower()
	if lower.startswith("/me "):
		text = text[4:]
		if arg["receive"]:
			self.print_line("In a page-pose to you, %s %s." % (arg["name"], text))
		else:
			self.print_line("You page-pose, \"%s\" to %s." % (text, arg["name"]))
	elif lower.startswith("/ooc "):
		text = text[5:]
		if arg["receive"]:
			self.print_line("%s pages, \"[OOC] %s\" to you." % (arg["name"], text))
		else:
			self.print_line("You page, \"[OOC] %s\" to %s." % (text, arg["name"]))
	else:
		if arg["receive"]:
			self.print_line("%s pages, \"%s\" to you." % (arg["name"], arg["text"]))
		else:
			self.print_line("You page, \"%s\" to %s." % (arg["text"], arg["name"]))

@protocol_command()
def fn_BAG(self, arg):
	pass

@protocol_command()
def fn_WHO(self, arg):
	if "you" in arg:
		self.entity_id = arg["you"]

	if "new_id" in arg:
		i = arg["new_id"]
		if i["id"] not in self.who:
			return
		self.who[i["new_id"]] = self.who[i["id"]]
		del i["id"]
		if i["id"] == self.entity_id:
			self.entity_id = i["new_id"]

	if "list" in arg:
		self.who = arg['list']

	if "add" in arg:
		i = arg["add"]
		_id = i["id"]
		if _id not in self.who:
			self.print_line("Joining: %s" % (i.get("name", str(i))))
		self.who[_id] = i

	if "remove" in arg and arg["remove"] in self.who:
		i = arg["remove"]
		self.print_line("Leaving: %s" % (self.who[i].get("name", str(i))))
		del self.who[i]

	if "update" in arg:
		i = arg["update"]
		_id = i["id"]
		if _id not in self.who:
			return
		if ("status" in i and i["status"] != self.who[_id].get("status", None)) or \
		("status" in i and i["status_message"] != self.who[_id].get("status_message", None)):
			if i["status"]:
				status_lower = status_name.lower()
				if status_lower == "away":
					status_name = "away"
				elif status_lower == "busy":
					status_name = "busy"
				elif status_lower == "ic":
					status_name = "in-character"
				elif status_lower == "iic":
					status_name = "looking to be in-character"
				elif status_lower == "ooc":
					status_name = "out of character"
				else:
					status_name = "'" + i["status"] + "'"
				line = "! %s set their status to %s" % (self.who[_id].name, status_name)
				if i["status_message"]:
					line += " (%s)" % i["status_message"]
				self.print_line(line)
			else:
				self.print_line("! %s cleared their status" % self.who[_id].name)
		self.who[_id].update(i)

@protocol_command()
def fn_IDN(self, arg):
	if self.mu_connection:
		self.print_line("Connected!")
		self.mu_connection.line_handler = self.mu_connection.connected_state_handler

@protocol_command()
def fn_MAI(self, arg):
	if "remote_map" in arg:
		return # Shouldn't be receiving these anyway
	self.map_id = arg["id"]
	self.map_info = arg

	self.print_line("Now entering: %s" % arg["name"])
	if "desc" in arg and arg["desc"]:
		self.print_line("  "+arg["desc"])
	if "edge_links" in arg and isinstance(arg["edge_links"], list):
		edge_links = arg["edge_links"]
		link_names = []
		for i in range(8):
			if edge_links[i]:
				link_names.append(["East", "SouthEast", "South", "SouthWest", "West", "NorthWest", "North", "NorthEast"][i])
		if len(link_names):
			self.print_line("Obvious Exits:")
			self.print_line("  %s" % ", ".join(link_names))
	if len(self.who) > 1:
		people = []
		for k,v in self.who.items():
			if v.get("name", None):
				people.append(v["name"])
		self.print_line("Contents: %s" % ", ".join(people))
