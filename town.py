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
		self.who = {}
		self.tilesets = {}
		self.tilesets_requested = set()

		# Map the user is on
		self.map_id = None
		self.map_info = {}
		self.map_width = None
		self.map_height = None
		self.map_turfs = None
		self.map_objs = None

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

	def print_map_rect_around_xy(self, x, y, w, h):
		x = max(0, x - w//2)
		y = max(0, y - h//2)
		if (x + w) >= self.map_width:
			w = self.map_width - x
		if (y + h) >= self.map_height:
			h = self.map_height - y
		self.print_map_rect(x, y, w, h)

	def lookup_atom(self, atom):
		if isinstance(atom, str):
			s = atom.split(":")
			if len(s) == 1:
				return self.tilesets[""].get(s[0], None)
			else:
				return self.tilesets.get(s[0], {}).get(s[1], None)
		return atom

	def print_map_rect(self, x_base, y_base, w, h):
		# Look for entities to draw
		entities = {}
		for k,e in self.who.items():
			entities[(e['x'], e['y'])] = e

		drawn_entities = []

		# Draw grid
		for y in range(y_base, y_base+h):
			line = ""
			for x in range(x_base, x_base+w):
				tile_char = "?"
				tile_fg = None
				tile_bg = None

				# Try drawing turf
				turf = self.map_turfs[x][y]
				if turf == None:
					turf = self.map_info['default']
				# Fetch data from the tileset if it's a tileset reference
				turf = self.lookup_atom(turf)
				if turf != None:
					# Use the "pic" to find what text to replace the tile with
					lookup = pic_to_text.get(tuple(turf['pic']), None)
					if lookup != None:
						if "fgcolorRGB" in lookup and self.mu_connection.rgb_color_enabled:
							tile_fg = ansi_fg_hex(lookup["fgcolorRGB"])
						else:
							tile_fg = ansi_fgcolors[lookup.get("fgcolor", "black")]
						if "bgcolorRGB" in lookup and self.mu_connection.rgb_color_enabled:
							tile_bg = ansi_bg_hex(lookup["bgcolorRGB"])
						else:
							tile_bg = ansi_bgcolors[lookup.get("bgcolor", "white")]

						if "utf8" in lookup and self.mu_connection.utf8_enabled:
							tile_char = lookup["utf8"]
						elif "ascii" in lookup:
							tile_char = lookup["ascii"]

				# Try drawing objects
				obj = self.map_objs[x][y]
				if isinstance(obj, list):
					obj = obj[-1]
				# Fetch data from the tileset if it's a tileset reference
				obj = self.lookup_atom(obj)
				if obj != None:
					# Use the "pic" to find what text to replace the tile with
					lookup = pic_to_text.get(tuple(obj['pic']), None)
					if lookup != None:
						if not lookup.get("ignore", False):
							if "fgcolorRGB" in lookup and self.mu_connection.rgb_color_enabled:
								tile_fg = ansi_fg_hex(lookup["fgcolorRGB"])
							elif "fgcolor" in lookup:
								tile_fg = ansi_fgcolors[lookup["fgcolor"]]
							if "bgcolorRGB" in lookup and self.mu_connection.rgb_color_enabled:
								tile_bg = ansi_bg_hex(lookup["bgcolorRGB"])
							elif "bgcolor" in lookup:
								tile_bg = ansi_bgcolors[lookup["bgcolor"]]

							if "utf8" in lookup and self.mu_connection.utf8_enabled:
								tile_char = lookup["utf8"]
							elif "ascii" in lookup:
								tile_char = lookup["ascii"]
					elif "name" in obj:
						tile_char = obj["name"][0]

				# Draw character if there is one
				entity = entities.get((x,y), None)
				if entity != None:
					if self.mu_connection.rgb_color_enabled:
						tile_fg = ansi_fg_hex(random_entity_colors[hash(entity['id']) % len(random_entity_colors)])
					else:
						tile_fg = "\x1b[%dm" % ([31, 32, 33, 35, 36, 37][hash(entity['id']) % 6])

					tile_bg = None
					if entity['id'] == self.entity_id:
						tile_char = '@'
					else:
						tile_char = entity['name'][0]
					drawn_entities.append((tile_fg, tile_char, entity['name']))

				# Put it in the line
				if self.mu_connection.color_enabled:
					if tile_fg == None or tile_bg == None:
						line += self.mu_connection.ansi_reset()
					if tile_fg:
						line += tile_fg
					if tile_bg:
						line += tile_bg
				line += tile_char

			self.print_line(line + self.mu_connection.ansi_reset())

		# Show a legend for what entities are what
		drawn_entity_line = ""
		for e in drawn_entities:
			fg, char, name = e
			if drawn_entity_line:
				drawn_entity_line += "|"
			if self.mu_connection.color_enabled:
				drawn_entity_line += '%s%s%s=%s' % (fg, char, self.mu_connection.ansi_reset(), name)
			else:
				drawn_entity_line += '%s=%s' % (char, name)
		self.print_line(drawn_entity_line)

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
def fn_MOV(self, arg):
	_id = arg["id"]
	if _id not in self.who:
		return
	e = self.who[_id]
	if "to" in arg:
		e["x"] = arg["to"][0]
		e["y"] = arg["to"][1]

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

	# Get ready to load the map
	self.map_width = arg["size"][0]
	self.map_height = arg["size"][1]
	self.map_turfs = []
	self.map_objs = []
	for x in range(0, self.map_width):
		self.map_turfs.append([None] * self.map_height)
		self.map_objs.append([None] * self.map_height)

@protocol_command()
def fn_MAP(self, arg):
	for t in arg["turf"]:
		self.map_turfs[t[0]][t[1]] = t[2]
	for o in arg["obj"]:
		self.map_objs[o[0]][o[1]] = o[2]

@protocol_command()
def fn_BLK(self, arg):
	# do copies
	for copy in arg.get("copy", []):
		do_turf = copy.get("turf", True)
		do_obj  = copy.get("obj", True)
		x1, y1, width, height = copy["src"]
		x2, y2                = copy["dst"]

		# turf
		if do_turf:
			copied = []
			for w in range(width):
				row = []
				for h in range(height):
					row.append(map.turfs[x1+w][y1+h])
				copied.append(row)

			for w in range(width):
				for h in range(height):
					self.map_turfs[x2+w][y2+h] = copied[w][h]
		# obj
		if do_obj:
			copied = []
			for w in range(width):
				row = []
				for h in range(height):
					row.append(map.objs[x1+w][y1+h])
				copied.append(row)

			for w in range(width):
				for h in range(height):
					self.map_objs[x2+w][y2+h] = copied[w][h]

	# Place the tiles
	for turf in arg.get("turf", []):
		x = turf[0]
		y = turf[1]
		a = turf[2]
		width = 1
		height = 1
		if len(turf) == 5:
			width = turf[3]
			height = turf[4]
		for w in range(width):
			for h in range(height):
				self.map_turfs[x+w][y+h] = a

	# Place the object lists
	for obj in arg.get("obj", []):
		x = obj[0]
		y = obj[1]
		a = obj[2]
		width = 1
		height = 1
		if len(turf) == 5:
			width = turf[3]
			height = turf[4]
		for w in range(width):
			for h in range(height):
				self.map_objs[x+w][y+h] = a

@protocol_command()
def fn_RSC(self, arg):
	for k,v in arg.get('tilesets', {}).items():
		self.tilesets[k] = v

@protocol_command()
def fn_TSD(self, arg):
	key = arg['id']
	data = arg['data']

	if isinstance(data, str):
		data = json.loads(data)
	
	self.tilesets[key] = data
	self.tilesets_requested.discard(key)

# -----------------------------------------------------------------------------
with open('ansimap.json', 'r') as f:
	pic_to_text = {}
	for e in json.load(f):
		pic = e['pic']
		if isinstance(pic[0], list):
			for p in pic:
				pic_to_text[tuple(p)] = e
		else:
			pic_to_text[tuple(pic)] = e

ansi_fgcolors = {
	"black": "\x1b[30m",
	"red": "\x1b[31m",
	"green": "\x1b[32m",
	"yellow": "\x1b[33m",
	"blue": "\x1b[34m",
	"magenta": "\x1b[35m",
	"cyan": "\x1b[36m",
	"white": "\x1b[37m"
}

ansi_bgcolors = {
	"black": "\x1b[40m",
	"red": "\x1b[41m",
	"green": "\x1b[42m",
	"yellow": "\x1b[43m",
	"blue": "\x1b[44m",
	"magenta": "\x1b[45m",
	"cyan": "\x1b[46m",
	"white": "\x1b[47m"
}

# Colors taken from island-joy-16
random_entity_colors = ["ffffff", "6df7c1", "11adc1", "5bb361", "a1e55a", "f7e476", "f99252", "cb4d68", "f48cb6", "f7b69e"]
