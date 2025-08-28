import base64
import configparser
import hashlib
import hmac
import json
import os
import sqlite3
import sys
from datetime import datetime

def readConfig():
	conf = {}
	config = configparser.ConfigParser(interpolation=None)
	config.read(configFile)
	confDef = {
		"main":{
			"db_location": "'./mikan.db'",
		},
		"web":{
			"ssl_crt_location": "''",
			"ssl_key_location": "''",
			"port": "'8089'",
			"host": "''",
			"token_valid_time": "'86400'",
			"secret": "'your_secret_key_here'",
			"strictlogin": 'false'
		}
	}

	for confGroup in confDef:
		if(confGroup in config) == False: config[confGroup] = {}
		for confName in confDef[confGroup]:
			conf[confName] = config.get(confGroup, confName, fallback=confDef[confGroup][confName]).replace("'","")
			config[confGroup][confName] = "'" + conf[confName] + "'"

	with open(configFile, 'w') as configfile:
		config.write(configfile)
	for key in conf.keys():
		if conf[key].startswith("./"):
			conf[key] = conf[key].replace("./",scriptLocation+"/",1)
	return conf

def checkDB():
	refTables = {
		"chapter": {
			"series":	 {"table":"series","col":"id"},
			"tgroup":	 {"table":"tgroup","col":"id"},
		},
	}
	tables = {
		"author": {
			"id":		 {"pri":True,  "type":"varchar", "def":""},
			"name":	   {"pri":False, "type":"varchar", "def":""},
			"favorite":   {"pri":False, "type":"boolean", "def":""},
			"ignore":	 {"pri":False, "type":"boolean", "def":""},
			"deleted":	{"pri":False, "type":"boolean", "def":""},
		},
		"chapter": {
			"series":	 {"pri":False, "type":"varchar", "def":""},
			"id":		 {"pri":True,  "type":"varchar", "def":""},
			"title":	  {"pri":False, "type":"varchar", "def":""},
			"volume":	 {"pri":False, "type":"varchar", "def":""},
			"chapter":	{"pri":False, "type":"varchar", "def":""},
			"tgroup":	 {"pri":False, "type":"varchar", "def":""},
			"language":   {"pri":False, "type":"varchar", "def":""},
			"time":	   {"pri":False, "type":"varchar", "def":""},
			"got":		{"pri":False, "type":"boolean", "def":""},
		},
		"fetch": {
			"id":		 {"pri":False, "type":"varchar", "def":""},
			"type":	   {"pri":False, "type":"integer", "def":""},
			"status":	 {"pri":False, "type":"varchar", "def":""},
		},
		"series": {
			"id":		 {"pri":True,  "type":"varchar", "def":""},
			"altId":	  {"pri":False, "type":"varchar", "def":""},
			"name":	   {"pri":False, "type":"varchar", "def":""},
			"lastUpdate": {"pri":False, "type":"varchar", "def":""},
			"favorite":   {"pri":False, "type":"boolean", "def":""},
			"forceName":  {"pri":False, "type":"varchar", "def":""},
			"author":	 {"pri":False, "type":"varchar", "def":""},
			"artist":	 {"pri":False, "type":"varchar", "def":""},
			"image":	  {"pri":False, "type":"blob",	"def":""},
			"imageName":  {"pri":False, "type":"varchar", "def":""},
			"fixedImage": {"pri":False, "type":"boolean", "def":""},
			"priority":   {"pri":False, "type":"integer", "def":""},
			"h":		  {"pri":False, "type":"boolean", "def":""},
			"lastCheck":  {"pri":False, "type":"varchar", "def":""},
			"nameWarn":   {"pri":False, "type":"boolean", "def":""},
			"source":	 {"pri":False, "type":"varchar", "def":""},
		},
		"settings": {
			"key":		{"pri":True,  "type":"varchar", "def":""},
			"name":	   {"pri":False, "type":"varchar", "def":""},
			"value":	  {"pri":False, "type":"varchar", "def":""},
			"user":	   {"pri":False, "type":"boolean", "def":""},
			"possible":   {"pri":False, "type":"varchar", "def":""},
		},
		"tgroup": {
			"id":		 {"pri":True,  "type":"varchar", "def":""},
			"name":	   {"pri":False, "type":"varchar", "def":""},
			"ignore":	 {"pri":False, "type":"boolean", "def":""},
			"fake":	   {"pri":False, "type":"boolean", "def":""},
			"deleted":	{"pri":False, "type":"boolean", "def":""},
		},
	}
	settings = {
		"dbVersion":	  {"name":"Database version", "value":"5.3", "user":"0", "possible":""},
		"saveDir":		{"name":"Save location", "value":"/media/Media/mikan/", "user":"1", "possible":""},
		"saveHDir":	   {"name":"Save location (H)", "value":"", "user":"1", "possible":""},
		"saveFormat":	 {"name":"", "value":"Individual Images", "user":"", "possible":"Individual Images"},
		"saveName":	   {"name":"Save format", "value":"_%{serie}%_/ch_%{chapter:>04}%__%{title: >s}%_ _%{lang_short}%__%[{group}]%_/_%{page:>03}%__%{extension}%_", "user":"1", "possible":""},
		"hSaveName":	  {"name":"Save format (h)", "value":"", "user":"1", "possible":""},
		"lastUpdateTime": {"name":"Last manga recheck", "value":"", "user":"0", "possible":""},
		"showCovers":	 {"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"showCoversH":	{"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"retryErrors":	{"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"retryTimes":	 {"name":"", "value":"100", "user":"0", "possible":""},
		"renameFolder":   {"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"languages":	  {"name":"Chapter download languages", "value":"en", "user":"1", "possible":""},
		"titleLanguages": {"name":"Manga title languages", "value":"en,jp", "user":"1", "possible":""},
		"coverDir":	   {"name":"Cover image location", "value":"_%{serie}%_/cover_%{extension}%_", "user":"1", "possible":""},
		"coverHDir":	  {"name":"Cover image location (H)", "value":"_%{serie}%_/cover_%{extension}%_", "user":"1", "possible":""},
		"saveCover":	  {"name":"Save cover image", "value":"yes", "user":"1", "possible":"yes,no"},
		"showH":		  {"name":"Display H", "value":"yes", "user":"1", "possible":"yes,no"},
		"appBGType":	  {"name":"App backgroud type", "value":"color", "user":"1", "possible":"cover,color"},
		"appBGCover":	 {"name":"App backgroud cover series id", "value":"", "user":"1", "possible":""},
		"appBGColor":	 {"name":"App backgroud color hex", "value":"000000", "user":"1", "possible":""},
		"webUser":		{"name":"Web cilent user", "value":"[]", "user":"0", "possible":""},
		"ignoreFake":	 {"name":"Ignore chapter from official/fake group", "value":"yes", "user":"1", "possible":"yes,no"},
	}
	try:
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		logged(f"Checking database from {config["db_location"]}...")
		logged(f"Checking table...")
		for table in tables:
			cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,))
			if cursor.fetchone() is None:
				logged(f"Creating {table} table...")
				t = f"CREATE TABLE {table} ("
				for col in tables[table]:
					t = t + f"{col} {tables[table][col]["type"]}"
					if tables[table][col]["pri"] == True:
						t = t + " UNIQUE PRIMARY KEY"
					if table in refTables:
						if col in refTables[table]:
							t = t + f" REFERENCES {refTables[table][col]["table"]}({refTables[table][col]["col"]})"
					t = t + ", "
				t = f"{t.rstrip(", ")})"
				cursor.execute(t)
				db.commit()
			else:
				cursor.execute(f"PRAGMA table_info({table})")
				cols = [c[1] for c in cursor.fetchall()]
				for col in tables[table]:
					if col not in cols:
						logged(f"Creating {col} in {table} table...")
						cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN {col} {tables[table][col]["type"]}")
						db.commit()

		logged(f"Checking settings table...")
		cursor.execute("SELECT key FROM settings")
		avaliableSettings = [s[0] for s in cursor.fetchall()]
		for setting in settings:
			settingKey = setting
			settingName = settings[setting]["name"]
			settingValue = settings[setting]["value"]
			settingUser = settings[setting]["user"]
			settingPossible = settings[setting]["possible"]
			if setting not in avaliableSettings:
				logged(f"Add settings {setting}...")
				cursor.execute("INSERT INTO settings (key,name,value,user,possible) VALUES (?,?,?,?,?)",(settingKey,settingName,settingValue,settingUser,settingPossible,))
				db.commit()
			else:
				cursor.execute("UPDATE settings SET name = ?, user = ?, possible = ? WHERE key = ?",(settingName,settingUser,settingPossible,settingKey,))
				db.commit()
			if settingKey == "dbVersion":
				cursor.execute("UPDATE settings SET value = ? WHERE key = ?",(settingValue,settingKey,))
				db.commit()

		cursor.close()
		db.close()
		logged("Database checking completed")
	except sqlite3.Error as e:
		logged(f"SQLite error: {e}")
		return False
	return True

def readSettings():
	checkDB()
	settings = {}
	db = sqlite3.connect(config["db_location"])
	db.execute('PRAGMA journal_mode=WAL;')
	cursor = db.cursor()
	cursor.execute("SELECT key,value FROM settings")
	for setting in cursor.fetchall():
		settings[setting[0]] = setting[1]
	return settings

def logged(*value):
	value = list(value)
	for i in range(len(value)):
		value[i] = str(value[i])
	time = datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
	text = "["+time+"] "+''.join(value)
	print(text)
	logLocDir = scriptLocation+"/log"
	logLoc = logLocDir+"/"+datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d')+".log"
	os.makedirs(logLocDir,exist_ok=True)
	with open(logLoc, "a") as file:
		file.write(text+"\n")

def checkArg(arg):
	data = {
		"input": {},
		"context": [
			{
				"var": "text",
				"type": str,
				"def": "default",
				"req": False
			}
		]
	}
	out = {"status":"", "data":{}}
	def err(r):
		out["status"] = "failed"
		out["data"]["msg"] = r
		return out
	def suc(r,d):
		out["status"] = "success"
		out["data"]["msg"] = r
		out["data"]["normal"] = d
		return out

	if isinstance(arg, dict) is not True: return err("[checkArg] function argument not dict")
	if ("input" in arg and "context" in arg) is not True: return err("[checkArg] input or context not in argument")
	if isinstance(arg["context"], list) is not True: return err("[checkArg] context not an list")
	if isinstance(arg["input"], dict) is not True: arg["input"] = {}

	input = arg["input"]
	context = arg["context"]

	for v in context:
		if isinstance(v, dict) is not True: return err("[checkArg] value include context is not a dict")
		if ("var" in v and "type" in v) is not True: return err("[checkArg] value include context is not complete")

		v["req"] = "req" in v if bool(v["req"]) else False

		if (v["req"]) is not True:
			try:
				if isinstance(input[v["var"]], v["type"]) is not True:
					return err(f"{v["var"]} is wrong type (require {str(v["type"])} but received {type(input[v["var"]])})")
			except KeyError:
				if v["type"] == list:
					if isinstance(v["def"], v["type"]): input[v["var"]] = v["def"]
					else: input[v["var"]] = []
				
				if v["type"] == tuple:
					if isinstance(v["def"], v["type"]): input[v["var"]] = v["def"]
					else: input[v["var"]] = ()
				
				if(v["type"] == dict):
					if isinstance(v["def"], v["type"]): input[v["var"]] = v["def"]
					else: input[v["var"]] = {}
				
				if(v["type"] == str):
					if isinstance(v["def"], v["type"]): input[v["var"]] = v["def"]
					else: input[v["var"]] = ""
				
				if(v["type"] == int):
					if isinstance(v["def"], v["type"]): input[v["var"]] = v["def"]
					else: input[v["var"]] = 0
				
				if(v["type"] == float):
					if isinstance(v["def"], v["type"]): input[v["var"]] = v["def"]
					else: input[v["var"]] = 0.0
				
				if(v["type"] == bool):
					if isinstance(v["def"], v["type"]): input[v["var"]] = v["def"]
					else: input[v["var"]] = False
		else:
			try:
				if isinstance(input[v["var"]], v["type"]) is not True:
					return err(f"{v["var"]} is wrong type (require {str(v["type"])} but received {type(input[v["var"]])})")

				if v["type"] == list and len(input[v["var"]]) <= 0:
					return err(f"{v["var"]} is require but received emply list")
				if v["type"] == tuple and len(input[v["var"]]) <= 0:
					return err(f"{v["var"]} is require but received emply tuple")
				if v["type"] == dict and len(input[v["var"]]) <= 0:
					return err(f"{v["var"]} is require but received emply dict")
				if v["type"] == str and len(input[v["var"]]) <= 0:
					return err(f"{v["var"]} is require but received emply str")
			except KeyError:
				return err(f"{v["var"]} is require")

	return suc("[checkArg] sucess",input)

def hashPassword(password):
	salt = os.urandom(16)
	pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
	return base64.b64encode(salt + pwdhash).decode('ascii')

def verifyPassword(stored_password, provided_password):
	stored_password = base64.b64decode(stored_password)
	salt = stored_password[:16]
	stored_pwdhash = stored_password[16:]
	pwdhash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
	return hmac.compare_digest(stored_pwdhash, pwdhash)

import sqlite3

def queryDB(select=["id"], table=["series"], where={}, whereopt="AND"):
	db = sqlite3.connect(config["db_location"])
	db.execute('PRAGMA journal_mode=WAL;')
	cr = db.cursor()
	q = "SELECT " + ", ".join(select).lower().replace("drop","").replace(";","") + " FROM " + ", ".join(table).lower().replace("drop","").replace(";","")
	if where:
		params = []
		parts = []
		wo = " " + whereopt.upper().replace("DROP","").replace(";","") + " "
		for key, value in where.items():
			if isinstance(value, (list, tuple)):
				if not value:
					parts.append("0=1")
				else:
					ph = ",".join("?" for _ in value)
					parts.append(f"{key} IN ({ph})")
					params.extend(value)
			else:
				parts.append(f"{key} = ?")
				params.append(value)
		q += " WHERE " + wo.join(parts)
		cr.execute(q, params)
	else:
		cr.execute(q)

	out = [dict(zip([c[0] for c in cr.description] if "*" in select or any(' ' in s for s in select) else select, row)) for row in cr.fetchall()]
	cr.close()
	db.close()
	return out

def updateDB(values={},table=["series"], where={}, whereopt="AND"):
	db = sqlite3.connect(config["db_location"])
	db.execute('PRAGMA journal_mode=WAL;')
	cr = db.cursor()
	q = "UPDATE " + ", ".join(table).lower().replace("drop","").replace(";","")
	
	params = []
	if values:
		parts = []
		for key, value in values.items():
			if isinstance(value, (str,int,float,bool)):
				parts.append(f"{key} = ?")
				params.append(value)
		q += " SET " + ", ".join(parts)
	else:
		raise TypeError("No set value on update")
	if where:
		parts = []
		wo = " " + whereopt.upper().replace("DROP","").replace(";","") + " "
		for key, value in where.items():
			if isinstance(value, (list, tuple)):
				if not value:
					parts.append("0=1")
				else:
					ph = ",".join("?" for _ in value)
					parts.append(f"{key} IN ({ph})")
					params.extend(value)
			else:
				parts.append(f"{key} = ?")
				params.append(value)
		q += " WHERE " + wo.join(parts)
	else:
		raise TypeError("No where value on update")
	print(q)
	cr.execute(q, params)
	db.commit()
	cr.close()
	db.close()
	return True

def insereplaceDB(values={}, table="series"):
    if not values:
        raise TypeError("No values provided for INSERT OR REPLACE")

    db = sqlite3.connect(config["db_location"])
    db.execute('PRAGMA journal_mode=WAL;')
    cr = db.cursor()

    col = list(values.keys())
    val = ", ".join(["?" for _ in col])
    q = f"INSERT OR REPLACE INTO {", ".join(table).lower().replace("drop","").replace(";","")} ({', '.join(col)}) VALUES ({val})"

    params = [values[col] for col in col]
    cr.execute(q, params)

    db.commit()
    cr.close()
    db.close()
    return True

def serviceRun(function=lambda:None, interval=60, arg=()):
	import threading
	def wrapper():
		args = arg if isinstance(arg, tuple) else (arg,)
		function(*args)
		threading.Timer(interval, wrapper).start()
	threading.Timer(interval, wrapper).start()


class WatchedProgress:
	def __init__(self, initial_data=None):
		self._data = initial_data if initial_data is not None else {}

	def __setitem__(self, key, value):
		self._data[key] = value
		self.send(self._data)

	def __delitem__(self, key):
		if key in self._data:
			del self._data[key]
			self.send(self._data)
		else:
			logged(f"Key '{key}' not found for deletion")
			self.send(self._data)

	def __getitem__(self, key):
		return self._data[key]

	def __iter__(self):
		return iter(self._data)

	def __len__(self):
		return len(self._data)
	
	def send(self,data):
		pass

	def update(self, id, data={"status":"","progress":"0","subprogress":"0"}):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("SELECT name,forceName FROM series WHERE id = ?", (id,))
		name = cursor.fetchone()
		cursor.close()
		db.close()
		out = {}
		if name is None:
			out["name"] = id
		else:
			if name[1] is not None:
				out["name"] = name[1]
			else:
				out["name"] = name[0]
		out["status"] = data["status"] if "status" in data and data["status"] is not None else "Unknown"
		out["progress"] = data["progress"] if "progress" in data and data["progress"] is not None else "0"
		out["subprogress"] = data["subprogress"] if "subprogress" in data and data["subprogress"] is not None else "0"
		self._data[id] = out
		self.send(self._data)

	def to_dict(self):
		return self._data

	def __repr__(self):
		return repr(self._data)



scriptLocation = os.path.abspath(os.path.dirname(sys.argv[0]))
clients = []
progress = WatchedProgress()
envConf = os.getenv("MIKAN_CONFIG_FILE")
configFile = envConf if os.getenv("MIKAN_CONFIG_FILE") != None else scriptLocation+'/config.ini'
config = readConfig()
settings = readSettings()
userList = json.loads(settings["webUser"])
url = {
	"mangadex": {
		"url": "https://www.mangadex.org",
		"api": "https://api.mangadex.org",
		"image": "https://uploads.mangadex.org",
		"report": "https://api.mangadex.network/report"
	},
	"comick": {
		"url": "https://comick.io",
		"api": "https://api.comick.fun",
		"image": "https://meo.comick.pictures"
	}
}
provider = url.keys()
headers = {
	'User-Agent': f'mikan/1.1.0; {sys.platform})'
}
headersPost = headers.copy()
headersPost.update({
	'Content-Type': 'application/x-www-form-urlencoded'
})