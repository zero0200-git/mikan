import base64
import configparser
import hashlib
import hmac
import json
import os
import sqlite3
import sys
from datetime import datetime
import threading
import traceback

def readConfig():
	conf = {}
	config = configparser.ConfigParser(interpolation=None)
	config.read(configFile)
	confDef = {
		"main":{
			"db_location": "'./mikan.db'",
			"db_auto_backup_update": "'true'",
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
			"series":     {"table":"series","col":"id"},
			"tgroup":     {"table":"tgroup","col":"id"},
		},
	}
	tables = {
		"author": {
			"id":         {"pri":True,  "type":"varchar", "def":""},
			"name":       {"pri":False, "type":"varchar", "def":""},
			"favorite":   {"pri":False, "type":"boolean", "def":""},
			"ignore":     {"pri":False, "type":"boolean", "def":""},
			"deleted":    {"pri":False, "type":"boolean", "def":""},
		},
		"chapter": {
			"series":     {"pri":False, "type":"varchar", "def":""},
			"id":         {"pri":True,  "type":"varchar", "def":""},
			"title":      {"pri":False, "type":"varchar", "def":""},
			"volume":     {"pri":False, "type":"varchar", "def":""},
			"chapter":    {"pri":False, "type":"varchar", "def":""},
			"tgroup":     {"pri":False, "type":"varchar", "def":""},
			"language":   {"pri":False, "type":"varchar", "def":""},
			"time":       {"pri":False, "type":"varchar", "def":""},
			"got":        {"pri":False, "type":"boolean", "def":""},
		},
		"queue": {
			"id":         {"pri":True,  "type":"varchar", "def":""},
			"name":       {"pri":False, "type":"varchar", "def":""},
			"parent":     {"pri":False, "type":"varchar", "def":""},
			"source":     {"pri":True,  "type":"varchar", "def":""},
			"type":       {"pri":True,  "type":"varchar", "def":""},
			"status":     {"pri":False, "type":"varchar", "def":"pending"},
			"statusText": {"pri":False, "type":"varchar", "def":"pending"},
		},
		"series": {
			"id":         {"pri":True,  "type":"varchar", "def":""},
			"altId":      {"pri":False, "type":"varchar", "def":""},
			"name":       {"pri":False, "type":"varchar", "def":""},
			"lastUpdate": {"pri":False, "type":"varchar", "def":""},
			"favorite":   {"pri":False, "type":"boolean", "def":""},
			"forceName":  {"pri":False, "type":"varchar", "def":""},
			"author":     {"pri":False, "type":"varchar", "def":""},
			"artist":     {"pri":False, "type":"varchar", "def":""},
			"image":      {"pri":False, "type":"blob",    "def":""},
			"imageName":  {"pri":False, "type":"varchar", "def":""},
			"fixedImage": {"pri":False, "type":"boolean", "def":""},
			"priority":   {"pri":False, "type":"integer", "def":""},
			"h":          {"pri":False, "type":"boolean", "def":""},
			"lastCheck":  {"pri":False, "type":"varchar", "def":""},
			"nameWarn":   {"pri":False, "type":"boolean", "def":""},
			"source":     {"pri":True,  "type":"varchar", "def":""},
		},
		"settings": {
			"key":        {"pri":True,  "type":"varchar", "def":""},
			"name":       {"pri":False, "type":"varchar", "def":""},
			"value":      {"pri":False, "type":"varchar", "def":""},
			"user":       {"pri":False, "type":"boolean", "def":""},
			"possible":   {"pri":False, "type":"varchar", "def":""},
		},
		"tgroup": {
			"id":         {"pri":True,  "type":"varchar", "def":""},
			"name":       {"pri":False, "type":"varchar", "def":""},
			"ignore":     {"pri":False, "type":"boolean", "def":""},
			"fake":       {"pri":False, "type":"boolean", "def":""},
			"deleted":    {"pri":False, "type":"boolean", "def":""},
		},
		"locks": {
			"id":         {"pri":True,  "type":"varchar", "def":""},
			"pid":        {"pri":False, "type":"integer", "def":""},
			"timestamp":  {"pri":False, "type":"varchar", "def":""},
			"type":       {"pri":False, "type":"varchar", "def":""},
		},
	}
	settings = {
		"dbVersion":      {"name":"Database version (mikan.X)", "value":version+".9", "user":"0", "possible":""},
		"saveDir":        {"name":"Save location", "value":"./mikan/", "user":"1", "possible":""},
		"saveHDir":       {"name":"Save location (H)", "value":"./mikan/h/", "user":"1", "possible":""},
		"saveFormat":     {"name":"", "value":"Individual Images", "user":"", "possible":"Individual Images"},
		"saveName":       {"name":"Save format", "value":"_%{serie}%_/ch_%{chapter:>04}%__%{title: >s}%_ _%{lang_short}%__%[{group}]%_/_%{page:>03}%__%{extension}%_", "user":"1", "possible":""},
		"hSaveName":      {"name":"Save format (h)", "value":"_%{serie}%_/ch_%{chapter:>04}%__%{title: >s}%_ _%{lang_short}%__%[{group}]%_/_%{page:>03}%__%{extension}%_", "user":"1", "possible":""},
		"lastUpdateTime": {"name":"Last manga recheck", "value":"", "user":"0", "possible":""},
		"showCovers":     {"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"showCoversH":    {"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"retryErrors":    {"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"retryTimes":     {"name":"", "value":"100", "user":"0", "possible":""},
		"renameFolder":   {"name":"", "value":"yes", "user":"0", "possible":"yes,no"},
		"languages":      {"name":"Chapter download languages", "value":"en", "user":"1", "possible":""},
		"titleLanguages": {"name":"Manga title languages", "value":"en,jp", "user":"1", "possible":""},
		"coverDir":       {"name":"Cover image location", "value":"_%{serie}%_/cover_%{extension}%_", "user":"1", "possible":""},
		"coverHDir":      {"name":"Cover image location (H)", "value":"_%{serie}%_/cover_%{extension}%_", "user":"1", "possible":""},
		"saveCover":      {"name":"Save cover image", "value":"yes", "user":"1", "possible":"yes,no"},
		"showH":          {"name":"Display H", "value":"yes", "user":"1", "possible":"yes,no"},
		"appBGType":      {"name":"App backgroud type", "value":"color", "user":"1", "possible":"cover,color"},
		"appBGCover":     {"name":"App backgroud cover series id", "value":"", "user":"1", "possible":""},
		"appBGColor":     {"name":"App backgroud color hex", "value":"000000", "user":"1", "possible":""},
		"webUser":        {"name":"Web cilent user", "value":"{ }", "user":"0", "possible":""},
		"ignoreFake":     {"name":"Ignore chapter from official/fake group", "value":"yes", "user":"1", "possible":"yes,no"},
		"AutoQueue":      {"name":"Auto add new chapter to queue", "value":"yes", "user":"1", "possible":"yes,no"},
	}

	try:
		if os.path.isfile(config["db_location"]):
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT value FROM settings WHERE key='dbVersion'")
			result = cursor.fetchone()
			cursor.close()
			db.close()
			if result is None:
				raise AssertionError("Database version not found")
			elif result[0] != settings["dbVersion"]["value"]:
				raise AssertionError(f"Database version mismatch (expected {settings["dbVersion"]["value"]} but found {result[0]})")
		else:
			raise AssertionError("Database file not found")
	except Exception as e:
		logged(f"Database verify error: {e}")
		try:
			if config["db_auto_backup_update"].lower() == "true" and os.path.isfile(config["db_location"]) and os.access(os.path.dirname(config["db_location"]), os.W_OK):
				backupLoc = config["db_location"] + "_" + datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y%m%d%H%M%S') + ".bak"
				logged(f"Backing up database to {backupLoc}...")
				try:
					with open(config["db_location"], 'rb') as original_db:
						with open(backupLoc, 'wb') as backup_db:
							backup_db.write(original_db.read())
				except Exception as be:
					logged(traceback.format_exc())
					logged(f"Error during backup: {be}")
					logged(f"Cannot backup database, aborting update and exit...")
					sys.exit(1)
					return False
				logged("Backup completed")
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			logged(f"Checking database from {config["db_location"]}...")
			for table in tables:
				logged(f"Checking table {table}...")
				cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,))
				if cursor.fetchone() is None:
					logged(f"Creating {table} table...")
					t = f"CREATE TABLE {table} ("
					pri = []
					for col in tables[table]:
						t = t + f"{col} {tables[table][col]["type"].upper()} {"DEFAULT NULL" if "def" not in tables[table][col] or tables[table][col]["def"] is None else f" DEFAULT '{tables[table][col]["def"]}'"}"
						if tables[table][col]["pri"] == True:
							pri.append(col)
						if table in refTables:
							if col in refTables[table]:
								t = t + f" REFERENCES {refTables[table][col]["table"]}({refTables[table][col]["col"]})"
						t = t + ", "
					t = f"{t.rstrip(", ")}{"" if len(pri) == 0 else ", PRIMARY KEY(" + ",".join(pri) + ")"})"
					cursor.execute(t)
					db.commit()
				else:
					replace = False
					cursor.execute(f"PRAGMA table_info({table})")
					result = cursor.fetchall()
					tbCols = [c[1] for c in result]
					if len(result) != len(tables[table]):
						replace = True
					else:
						for col in result:
							if col[1] not in tables[table]:
								replace = True
								break
							elif col[2].lower() != tables[table][col[1]]["type"].lower():
								replace = True
								break
							elif col[4] is None and ("def" in tables[table][col[1]] and tables[table][col[1]]["def"] is not None):
								replace = True
								break
							elif col[5] < 1 and tables[table][col[1]]["pri"] == True:
								replace = True
								break
					if replace == True:
						logged(f"Needing to update table {table}...")
						for col in tbCols:
							if col not in tables[table]:
								logged(f"Cannot update table {table} automatically because {col} is no longer in new db version, need manual update, aborting...")
								raise Exception(f"Cannot update table {table} because {col} is no longer in new db version")
						logged(f"Renaming table {table} to {table}_old...")
						cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
						db.commit()
						logged(f"Creating new table {table}...")
						t = f"CREATE TABLE {table} ("
						pri = []
						for col in tables[table]:
							t = t + f"{col} {tables[table][col]["type"].upper()} {"DEFAULT NULL" if "def" not in tables[table][col] or tables[table][col]["def"] is None else f" DEFAULT '{tables[table][col]["def"]}'"}"
							if tables[table][col]["pri"] == True:
								pri.append(col)
							if table in refTables:
								if col in refTables[table]:
									t = t + f" REFERENCES {refTables[table][col]["table"]}({refTables[table][col]["col"]})"
							t = t + ", "
						t = f"{t.rstrip(", ")}{"" if len(pri) == 0 else ", PRIMARY KEY(" + ",".join(pri) + ")"})"
						cursor.execute(t)
						db.commit()
						logged(f"Copying data from {table}_old to {table}...")
						mv = f"INSERT INTO {table} ({",".join(tbCols)}) SELECT {",".join(tbCols)} FROM {table}_old"
						cursor.execute(mv)
						db.commit()
						logged(f"Dropping old table {table}_old...")
						cursor.execute(f"DROP TABLE {table}_old")
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
		except (sqlite3.Error,Exception) as e:
			logged(traceback.format_exc())
			logged(f"Error: {e}")
			logged("Database checking failed, exiting...")
			sys.exit(1)
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
	try:
		with open(logLoc, "a") as file:
			file.write(text+"\n")
	except Exception as e:
		logged(traceback.format_exc())
		print(f"Error writing log to {logLoc}: {e}")

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

		v["req"] = bool(v["req"]) if "req" in v else False

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
			if isinstance(value, (str,int,float,bool,type(None))):
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
	cr.execute(q, params)
	db.commit()
	cr.close()
	db.close()
	return True

def insereplaceDB(values={}, table=["series"]):
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

def deleteDB(where={}, table="series", whereopt="AND"):
	db = sqlite3.connect(config["db_location"])
	db.execute('PRAGMA journal_mode=WAL;')
	cr = db.cursor()
	q = "DELETE FROM " + ", ".join(table).lower().replace("drop","").replace(";","")
	
	params = []
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
		raise TypeError("No where value on delete")
	cr.execute(q, params)
	db.commit()
	cr.close()
	db.close()
	return True

def serviceRun(func=lambda:None, interval=60, arg=()):
	import threading
	def wrapper():
		args = arg if isinstance(arg, tuple) else (arg,)
		func(*args)
		threading.Timer(interval, wrapper).start()
	threading.Timer(interval, wrapper).start()

def dbLock(lock_id, lock_type="queue"):
    try:
        db = sqlite3.connect(config["db_location"])
        cr = db.cursor()
        
        cr.execute("DELETE FROM locks WHERE timestamp < datetime('now', '-1 hour')")
        cr.execute("SELECT pid FROM locks WHERE id=? AND type=?", (lock_id, lock_type))
        
        row = cr.fetchone()
        if row:
            try:
                os.kill(row[0], 0)
                return False
            except OSError:
                cr.execute("DELETE FROM locks WHERE id=? AND type=?", (lock_id, lock_type))

        cr.execute("INSERT INTO locks (id, pid, timestamp, type) VALUES (?, ?, datetime('now'), ?)", (lock_id, os.getpid(), lock_type))
        db.commit()
        return True
    except sqlite3.Error:
        return False
    finally:
        db.close()

def dbUnlock(lock_id, lock_type="queue"):
    try:
        db = sqlite3.connect(config["db_location"])
        cr = db.cursor()
        cr.execute("DELETE FROM locks WHERE id=? AND type=? AND pid=?", (lock_id, lock_type, os.getpid()))
        db.commit()
    except sqlite3.Error:
        pass
    finally:
        db.close()

class WatchedProgress:
	def __init__(self):
		self._data = {}
		self._data["update"] = {}
		self._data["updateNo"] = []
		for q in queryDB(select=["id","parent","name","source","type","status","statusText"],table=["queue"]):
			out = {}
			out["name"] = q["name"] if "name" in q and q["name"] is not None else "Unknown"
			out["status"] = q["status"] if "status" in q and q["status"] is not None else "Unknown"
			out["parent"] = q["parent"] if "parent" in q and q["parent"] is not None else ""
			out["provider"] = q["source"] if "source" in q and q["source"] is not None else "Unknown"
			out["type"] = q["type"] if "type" in q and q["type"] is not None else "Unknown"
			out["statusText"] = q["statusText"] if "statusText" in q and q["statusText"] is not None else "Unknown"
			out["progress"] = "100" if "status" in q and q["status"] == "done" else "0"
			out["subprogress"] = "100" if "status" in q and q["status"] == "done" else "0"
			rmm = max(10, min(100, len(self._data["updateNo"])))
			rmc = 0
			while self._data["updateNo"].count(q["id"]) >= 1 and rmc < rmm: (self._data["updateNo"].remove(q["id"]) if q["id"] in self._data["updateNo"] else None); rmc += 1
			self._data["updateNo"].insert(0,q["id"])
			self._data["update"][q["id"]] = out

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

	def updatelist(self, data={"id":"","name":"","parent":"","provider":"","type":"","status":"pending","statusText":"","progress":"0","subprogress":"0"}):
		dataC = checkArg({
			"input": data,
			"context": [
				{"var":"id", "type":str, "def":"", "req":True},
				{"var":"name", "type":str, "def":"", "req":True},
				{"var":"parent", "type":str, "def":"", "req":False},
				{"var":"provider", "type":str, "def":"", "req":False},
				{"var":"type", "type":str, "def":"", "req":True},
				{"var":"status", "type":str, "def":"pending", "req":True},
				{"var":"statusText", "type":str, "def":"", "req":False},
				{"var":"progress", "type":str, "def":"0", "req":False},
				{"var":"subprogress", "type":str, "def":"0", "req":False},
			]
		})
		if dataC["status"] != "success":
			logged(f"WatchedProgress update error: {dataC['data']['msg']}")
			return self._data
		data = dataC["data"]["normal"]

		out = {}
		out["name"] = data["name"] if "name" in data and data["name"] is not None else "Unknown"
		out["status"] = data["status"] if "status" in data and data["status"] is not None else "Unknown"
		out["parent"] = data["parent"] if "parent" in data and data["parent"] is not None else ""
		out["provider"] = data["provider"] if "provider" in data and data["provider"] is not None else ""
		out["type"] = data["type"] if "type" in data and data["type"] is not None else ""
		out["statusText"] = data["statusText"] if "statusText" in data and data["statusText"] is not None else "Unknown"
		out["progress"] = data["progress"] if "progress" in data and data["progress"] is not None else "0"
		out["subprogress"] = data["subprogress"] if "subprogress" in data and data["subprogress"] is not None else "0"
		insereplaceDB(values={"id":data["id"],"parent":out["parent"],"name":out["name"],"source":out["provider"],"type":out["type"],"status":out["status"],"statusText":out["statusText"]},table=["queue"])
		rmm = max(10, min(100, len(self._data["updateNo"])))
		rmc = 0
		while self._data["updateNo"].count(data["id"]) >= 1 and rmc < rmm: (self._data["updateNo"].remove(data["id"]) if data["id"] in self._data["updateNo"] else None); rmc += 1
		self._data["updateNo"].insert(0,data["id"])
		self._data["update"][data["id"]] = out
		self.send(self._data)
		return self._data

	def to_dict(self):
		return self._data

	def clearDone(self):
		doneIds = [id for id, info in self._data["update"].items() if info["status"] == "done"]
		for id in doneIds:
			del self._data["update"][id]
			while id in self._data["updateNo"]:
				self._data["updateNo"].remove(id)
		self.send(self._data)
		return self._data

	def clear(self):
		self._data = {}
		self._data["update"] = {}
		self._data["updateNo"] = []
		self.send(self._data)
		return self._data

	def __repr__(self):
		return repr(self._data)

scriptLocation = os.path.abspath(os.path.dirname(sys.argv[0]))
version = "1.2.2"
envConf = os.getenv("MIKAN_CONFIG_FILE")
configFile = envConf if os.getenv("MIKAN_CONFIG_FILE") != None else scriptLocation+'/config.ini'
config = readConfig()
settings = readSettings()
userList = json.loads(settings["webUser"])
clients = []
progress = WatchedProgress()
queueStopFlag = False
queueStopLock = threading.Lock()

def set_queue_stop(val: bool):
	global queueStopFlag
	with queueStopLock:
		queueStopFlag = bool(val)
	return True
def isQueueStop():
	with queueStopLock:
		return queueStopFlag

url = {
	"mangadex": {
		"url": "https://www.mangadex.org",
		"api": "https://api.mangadex.org",
		"image": "https://uploads.mangadex.org",
		"report": "https://api.mangadex.network/report"
	},
	# "comick": {
	# 	"url": "https://comick.io",
	# 	"api": "https://api.comick.fun",
	# 	"image": "https://meo.comick.pictures"
	# }
}
provider = url.keys()
headers = {
	'User-Agent': f'mikan/{version}; ({sys.platform})'
}
headersPost = headers.copy()
headersPost.update({
	'Content-Type': 'application/x-www-form-urlencoded'
})