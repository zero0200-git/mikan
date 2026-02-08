import base64
from collections.abc import Callable
import configparser
from datetime import datetime
from functools import lru_cache
import hashlib
import hmac
import importlib
import inspect
import json
import os
import re
import sqlite3
import sys
import threading
import time
import traceback
from typing import Any
import urllib
import urllib.request
import urllib.parse
import urllib.error
from src.ModuleTemplate import ModuleTemplate


class Log:
	web = False
	def logged(self, *value) -> None:
		value = list(value)
		for i in range(len(value)):
			value[i] = str(value[i])
		time = datetime.fromisoformat(datetime.now().isoformat()).strftime("%Y-%m-%d %H:%M:%S")
		text = f"[{time}] {"".join(value)}"
		print(text)
		logDir = Base().getInfo("scriptLocation")+"/log"
		logFile = logDir+"/"+datetime.fromisoformat(datetime.now().isoformat()).strftime("%Y-%m-%d")+".log"
		if os.path.isdir(logDir) != True:
			os.makedirs(logDir,exist_ok=True)
		try:
			with open(logFile, "a") as file:
				file.write(text+"\n")
			if self.web:
				from mdweb import sendMessage
				sendMessage("".join(value), timestamp=time)
		except Exception as e:
			print(traceback.format_exc())
			print(f"Error writing log to {logFile}: {e}")

class Modules(ModuleTemplate):
	_allModule:dict = {}
	def __init__(self, logged:Log|Callable|None = None) -> None:
		self.logged = logged if logged != None else Base().logged
		self._loadedModule: ModuleTemplate|None = None
		moduleDir = Base().getInfo("scriptLocation") + "/src/module/"
		moduleList = [os.path.join(moduleDir,f) for f in os.listdir(moduleDir) if os.path.isfile(os.path.join(moduleDir,f))]
		for modulePath in moduleList:
			moduleName = os.path.basename(modulePath)[:-3]
			for name,classFunc in inspect.getmembers(importlib.import_module("src.module."+moduleName),inspect.isclass):
				if issubclass(classFunc,ModuleTemplate) and hasattr(classFunc,"name") and classFunc.name != ModuleTemplate.name:
					self._allModule.update({classFunc.name:classFunc})

	def getModuleList(self) -> list:
		return list(self._allModule.keys())

	def _loadedModuleCheck(self) -> bool:
		if isinstance(self._loadedModule, ModuleTemplate):
			return True
		else:
			self.logged("module is not loaded")
			self.logged("please load module using \"loadModule\" function")
			return False

	def loadModule(self, moduleName:str, **args) -> None:
		if moduleName in self._allModule:
			self._loadedModule = self._allModule[moduleName](**args)
			self.logged("load module: ",moduleName," success")
		else:
			self.logged("cannot load module: ",moduleName)

	def search(self, keyword:str) -> list:
		if self._loadedModuleCheck() == False:
			return super().search(keyword)
		return self._loadedModule.search(keyword)

	def getSerieInfo(self, serieid:str) -> dict:
		if self._loadedModuleCheck() == False:
			return super().getSerieInfo(serieid)
		return self._loadedModule.getSerieInfo(serieid)

	def getAuthorInfo(self, authorid:str) -> dict:
		if self._loadedModuleCheck() == False:
			return super().getAuthorInfo(self, authorid)
		return self._loadedModule.getAuthorInfo(authorid)

	def getChapterImg(self, chapterid:str) -> list:
		if self._loadedModuleCheck() == False:
			return super().getChapterImg(self, chapterid)
		return self._loadedModule.getChapterImg(chapterid)

	def getChapterList(self, serieid:str) -> list:
		if self._loadedModuleCheck() == False:
			return super().getChapterList(self, serieid)
		return self._loadedModule.getChapterList(serieid)

class Progress:
	web:bool = False
	_progressLock = threading.Lock()
	def __init__(self,logged:Log|Callable=Log.logged):
		self.logged:Log|Callable = logged
		self._data:dict = {}
		self._data["update"] = {}
		self._data["updateNo"] = []
		for q in Base().queryDB(select=["id","parent","name","source","type","status","statusText"],table=["queue"]):
			out = {}
			out["id"] = q["id"] if "id" in q and q["id"] is not None else "Unknown"
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
			self.logged(f"Key '{key}' not found for deletion")
			self.send(self._data)

	def __getitem__(self, key):
		return self._data[key]

	def __iter__(self):
		return iter(self._data)

	def __len__(self):
		return len(self._data)
	
	def send(self,data):
		if self.web:
			from mdweb import sendMessage
			sendMessage(data,msgType="progress")

	def updatelist(self, data={"id":"","name":"","parent":"","provider":"","type":"","status":"pending","statusText":"","progress":"0","subprogress":"0"}):
		dataC = Base().checkArg({
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
			self.logged(f"WatchedProgress update error: {dataC['data']['msg']}")
			return self._data
		data = dataC["data"]["normal"]

		out = {}
		out["id"] = data["id"] if "id" in data and data["id"] is not None else "Unknown"
		out["name"] = data["name"] if "name" in data and data["name"] is not None else "Unknown"
		out["status"] = data["status"] if "status" in data and data["status"] is not None else "Unknown"
		out["parent"] = data["parent"] if "parent" in data and data["parent"] is not None else ""
		out["provider"] = data["provider"] if "provider" in data and data["provider"] is not None else ""
		out["type"] = data["type"] if "type" in data and data["type"] is not None else ""
		out["statusText"] = data["statusText"] if "statusText" in data and data["statusText"] is not None else "Unknown"
		out["progress"] = data["progress"] if "progress" in data and data["progress"] is not None else "0"
		out["subprogress"] = data["subprogress"] if "subprogress" in data and data["subprogress"] is not None else "0"
		with self._progressLock:
			Base().insereplaceDB(values={"id":data["id"],"parent":out["parent"],"name":out["name"],"source":out["provider"],"type":out["type"],"status":out["status"],"statusText":out["statusText"]},table=["queue"])
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
		with self._progressLock:
			doneID = [id for id, info in self._data["update"].items() if info["status"] == "done"]
			for id in doneID:
				del self._data["update"][id]
				while id in self._data["updateNo"]:
					self._data["updateNo"].remove(id)
			self.send(self._data)
			return self._data

	def clear(self):
		with self._progressLock:
			self._data = {}
			self._data["update"] = {}
			self._data["updateNo"] = []
			self.send(self._data)
			return self._data

	def __repr__(self):
		return repr(self._data)

class Base:
	_availableInfo = ["scriptLocation","version","configFile","config","settings","userList","clients","progress","provider","headers","headersPost","queueStopFlag","queueStopLock","runningQueue"]
	_availableInfoReq = {"configFile":["scriptLocation"],"userList":["settings"],"headers":["version"],"headersPost":["headers"]}
	_baseVars = {}
	_baseVarsLock = threading.RLock()
	logged:Log|Callable|None = None

	def __init__(self, logged:Log|Callable|None=Log().logged) -> None:
		self.logged:Log|Callable|None = logged if logged != None else Base.logged if isinstance(self.logged,Log) != True or isinstance(self.logged,Callable) != True else self.logged

	def initInfo(self, vars:list=[],force:bool=False) -> None:
		check=self.checkArg({
			"input": {"vars": vars, "force": force},
			"context": [
				{"var":"vars", "type":list, "def":self._availableInfo},
				{"var":"force", "type":bool, "def":False}
			]
		})
		vars = check["data"]["normal"]["vars"]
		force = check["data"]["normal"]["force"]
		for v in vars:
			if v not in Base._availableInfo:
				self.logged("cannot init info: not in available info")
			if v in Base._availableInfoReq:
				self.initInfo(Base._availableInfoReq[v],force)
			if v in Base._availableInfo and (v not in Base._baseVars or force):
				with Base._baseVarsLock:
					if "scriptLocation" == v:
						Base._baseVars[v] = os.path.abspath(os.path.dirname(sys.argv[0]))
					if "version" == v:
						Base._baseVars[v] = "1.3.0"
					if "configFile" == v:
						Base._baseVars[v] = os.getenv("MIKAN_CONFIG_FILE") if os.getenv("MIKAN_CONFIG_FILE") != None else Base._baseVars["scriptLocation"]+'/config.ini'
					if "config" == v:
						Base._baseVars[v] = Base.readConfig(self)
					if "settings" == v:
						Base._baseVars[v] = Base.readSettings(self)
					if "userList" == v:
						Base._baseVars[v] = json.loads(Base._baseVars["settings"]["webUser"])
					if "clients" == v:
						Base._baseVars[v] = []
					if "progress" == v:
						Base._baseVars[v] = Progress(logged=Base.logged)
					if "provider" == v:
						Base._baseVars[v] = Modules().getModuleList()
					if "headers" == v:
						Base._baseVars[v] = {'User-Agent': f'mikan/{Base._baseVars["version"]}; ({sys.platform})'}
					if "headersPost" == v:
						h = Base._baseVars["headers"].copy()
						h.update({'Content-Type': 'application/json'})
						Base._baseVars[v] = h
					if "queueStopFlag" == v:
						Base._baseVars[v] = False
					if "queueStopLock" == v:
						Base._baseVars[v] = threading.Lock()
					if "runningQueue" == v:
						Base._baseVars[v] = False

	def getInfo(self, key:str) -> Any:
		if key not in Base._availableInfo:
			raise NameError("No info name:",key)
		else:
			if key not in Base._baseVars:
				self.initInfo([key])
			return Base._baseVars[key]

	def setInfo(self, key:str, value:Any) -> Any:
		if key not in Base._availableInfo:
			raise NameError("No info name:",key)
		else:
			if key not in Base._baseVars:
				self.initInfo([key])
			baseType = type(Base._baseVars[key])
			valueType = type(value)
			if baseType != valueType:
				raise TypeError("Not same type",baseType,":",valueType)
			with Base._baseVarsLock:
				Base._baseVars[key] = value

	@staticmethod
	@lru_cache(maxsize=20)
	def requestGet(url:str, logged:Callable=Log().logged) -> dict:
		base = Base(logged=logged)
		headers = base.getInfo("headers")
		logged(f"request: {url}")
		r = {}
		req = urllib.request.Request(url, headers=headers)
		try:
			with urllib.request.urlopen(req) as response:
				r["status"] = response.getcode()
				r["data"] = response.read()
				r["header"] = dict(response.headers)
				try:
					r["text"] = r["data"].decode("utf-8")
				except:
					r["text"] = ""
				try:
					r["json"] = json.loads(r["data"])
				except:
					r["json"] = {}
			logged(f"request: {url} complete")
		except urllib.error.HTTPError as e:
			r["status"] = e.code
			r["text"] = ""
			r["json"] = {}
			logged(f"request: {url} error")
		return r

	@staticmethod
	def requestPost(url:str, logged:Callable=Log().logged, data:dict={}) -> dict:
		base = Base(logged=logged)
		headers = base.getInfo("headersPost")
		postData = urllib.parse.urlencode(data).encode()
		logged(f"request: {url}")
		r = {}
		req = urllib.request.Request(url, headers=headers, data=postData, method="POST")
		try:
			with urllib.request.urlopen(req) as response:
				r["status"] = response.getcode()
				r["data"] = response.read()
				r["header"] = response.headers
				try:
					r["text"] = r["data"].decode("utf-8")
				except:
					r["text"] = ""
				try:
					r["json"] = json.loads(r["data"])
				except:
					r["json"] = {}
			logged(f"request: {url} complete")
		except urllib.error.HTTPError as e:
			r["status"] = e.code
			r["data"] = ""
			r["text"] = ""
			r["json"] = {}
			logged(f"request: {url} error")
		return r

	def downloadPage(self, url:str, location:str, progressCallback:Callable|None=None) -> dict:
		speedUnit = ["B","KB","MB","GB","TB","PB"]
		speed = 0
		speedUC = 0
		textLength = 0
		headers = self.getInfo("headers")
		out = {}
		if location != "" and url != "":
			os.makedirs(os.path.dirname(location),exist_ok=True)
			req = urllib.request.Request(url, headers=headers)
			self.logged(f"request: {url}")
			try:
				with urllib.request.urlopen(req, timeout=10) as r:
					startTime = time.time()
					out["url"] = url
					out["status"] = r.getcode()
					out["header"] = r.headers
					out["size"] = int(out["header"].get("Content-Length", 0))
					out["cache"] = str(out["header"].get("X-Cache", "MISS"))
					out["data"] = bytes()
					out["download"] = 0
					out["block"] = 4096
					out["start"] = int(time.time())
					out["usedtime"] = 0
					out["speed"] = 0
					out["percent"] = 0

					if out["status"] == 200:
						with open(location+".tmp", "wb") as file:
							while True:
								data = r.read(out["block"])
								if not data:
									break
								file.write(data)
								out["data"] += data
								out["download"] += len(data)
								out["usedtime"] = (time.time() - out["start"]) if (time.time() - out["start"])>1 else 1
								out["speed"] = out["download"] / (time.time() - startTime)

								if out["speed"] > 4_000_000:
									out["block"] = 65536
								elif out["speed"] > 1_000_000:
									out["block"] = 16384
								else:
									out["block"] = 4096
								
								out["percent"] = out["download"] / out["size"] * 100 if out["size"] else 0
								speed = out["speed"]
								speedUC = 0
								while int(speed) > 1000 and speedUC < len(speedUnit)-1:
									speed = speed/1000
									speedUC += 1
								text = f"\rDownloading: {out["percent"]:.2f}% ({out["download"]}/{out["size"]} bytes) | Speed: {speed:.2f} {speedUnit[speedUC]}/s"
								sys.stdout.write(f"\r{" "*textLength}")
								sys.stdout.write(text)
								sys.stdout.flush()
								textLength = len(text)
								if isinstance(progressCallback,Callable):
									def run_callback():
										try:
											progressCallback(out)
										except Exception as e:
											self.logged(f"Callback error: {e}")
									callbackThread = threading.Thread(target=run_callback, daemon=True)
									callbackThread.start()
									callbackThread.join(timeout=5)
									if callbackThread.is_alive():
										self.logged(f"Callback timeout after 5 seconds")
							sys.stdout.write("\n")
							sys.stdout.flush()
							file.flush()
							file.close()

							os.rename(location+".tmp", location)
							self.logged(f"Image saved as {location}")
					else:
						self.logged("Failed to download image. Status code:", out["status"])
						return out
			except urllib.error.HTTPError as e:
				self.logged(f"HTTP Error: {e.code} - {e.reason} for {url}")
				out["status"] = e.code
			except urllib.error.URLError as e:
				self.logged(f"URL Error: {e.reason} for {url}")
				out["status"] = 500
			except Exception as e:
				self.logged(traceback.format_exc())
				self.logged(f"Error downloading {url}: {str(e)}")
				out["status"] = 500
		else:
			out["status"] = 404
			self.logged(f"downloadPage no url or location")
		return out

	def customFormat(self, format:str, **data) -> str:
		""" format
		serie #w
		group #w
		authors #w
		artists #w
		volume #w
		chapte #w
		title #w
		page #w
		extensionion #w
		lang_short #w
		"""
		out = {}
		matches = re.findall(r"_%(.*?)\{(.*?)\}(.*?)%_", format)
		result = ""
		last_end = 0
		for match in re.finditer(r"_%(.*?)\{(.*?)\}(.*?)%_", format):
			start, end = match.span()
			result += format[last_end:start]
			result += f"{{{match[2]}}}"
			last_end = end

		result += format[last_end:]
		format = result

		for d in [[m[0], m[1], m[2]] for m in matches]:
			placeholders = re.findall(r"(\w+)(:[^}]*)?", d[1])
			for key, spec in placeholders:
				value = data.get(key, "")
				value = "" if (value is None) or (value=="") else d[0]+str(value)+d[2]
				value = re.sub(r"([\^\<\>\;\?\"\*\|\/\\]*)", "", re.sub(r"(\s*[\:]+\s*)", " - ", value))

				if spec:
					if ": >" in spec:
						value = f" {value}" if value else ""
					elif spec.startswith(":>") or spec.startswith(":0"):
						width = int(re.search(r"(\d+)", spec).group(1))
						if value.replace(".", "", 1).isdigit():
							if "." in value:
								integer_part, decimal_part = value.split(".")
								value = f"{int(integer_part):0{width}}.{decimal_part}"
							else:
								value = f"{int(value):0{width}}"
						else:
							value = f"{value:>{width}}"

				out[key] = value
		return format.format(**out)

	def checkArg(self, arg:dict) -> dict:
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
		def scs(r,d):
			out["status"] = "success"
			out["data"]["msg"] = r
			out["data"]["normal"] = d
			return out

		if isinstance(arg, dict) is not True: return err("[checkArg] function argument not dict")
		if ("input" in arg and "context" in arg) is not True: return err("[checkArg] input or context not in argument")
		if isinstance(arg["context"], list) is not True: return err("[checkArg] context not an list")
		if isinstance(arg["input"], dict) is not True: arg["input"] = {}

		input = arg["input"]
		inputOut = {}
		context = arg["context"]

		for v in context:
			if isinstance(v, dict) is not True: return err("[checkArg] value include context is not a dict")
			if ("var" in v and "type" in v) is not True: return err("[checkArg] value include context is not complete")

			v["req"] = bool(v["req"]) if "req" in v else False

			if (v["req"]) is not True:
				if v["var"] in input:
					if isinstance(input[v["var"]], v["type"]) is not True:
						return err(f"{v["var"]} is wrong type (require {str(v["type"])} but received {type(input[v["var"]])})")
					inputOut[v["var"]] = input[v["var"]]
				else:
					if v["type"] == list:
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = []
					
					if v["type"] == tuple:
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = ()
					
					if(v["type"] == dict):
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = {}
					
					if(v["type"] == str):
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = ""
					
					if(v["type"] == int):
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = 0
					
					if(v["type"] == float):
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = 0.0
					
					if(v["type"] == bool):
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = False

					if(v["type"] == Callable):
						if isinstance(v["def"], v["type"]): inputOut[v["var"]] = v["def"]
						else: inputOut[v["var"]] = lambda:""
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
					inputOut[v["var"]] = input[v["var"]]
				except KeyError:
					return err(f"{v["var"]} is require")

		return scs("[checkArg] sucess",inputOut)

	def queryDB(self, select:list=["id"], table:list=["series"], where:dict={}, whereopt:str="AND") -> list:
		db = sqlite3.connect(self.getInfo("config")["db_location"])
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

	def updateDB(self, values:dict={}, table:list=["series"], where:dict={}, whereopt:str="AND") -> None:
		db = sqlite3.connect(self.getInfo("config")["db_location"])
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

	def insereplaceDB(self, values:dict={}, table:list=["series"]) -> None:
		if not values:
			raise TypeError("No values provided for INSERT OR REPLACE")

		db = sqlite3.connect(self.getInfo("config")["db_location"])
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

	def deleteDB(self, where:dict={}, table:list=["series"], whereopt:str="AND") -> None:
		db = sqlite3.connect(self.getInfo("config")["db_location"])
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

	def readConfig(self, configFilePath:str="") -> dict:
		if configFilePath == "":
			configFilePath = self.getInfo("configFile")
		conf = {}
		config = configparser.ConfigParser(interpolation=None)
		config.read(configFilePath)
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

		confCount = 0
		for confGroup in confDef:
			if(confGroup in config) == False:
				config[confGroup] = {}
				confCount += 1
			for confName in confDef[confGroup]:
				if (confName in config[confGroup]) == False:
					confCount += 1
				conf[confName] = config.get(confGroup, confName, fallback=confDef[confGroup][confName]).replace("'","")
				config[confGroup][confName] = "'" + conf[confName] + "'"

		if confCount > 0:
			with open(configFilePath, 'w') as configfile:
				config.write(configfile)
		for key in conf.keys():
			if conf[key].startswith("./"):
				conf[key] = conf[key].replace("./",self.getInfo("scriptLocation")+"/",1)
		return conf

	def readSettings(self) -> dict:
		self.checkDB()
		settings = {}
		settingdb = self.queryDB(select=["key","value"],table=["settings"])
		for setting in settingdb:
			settings[setting["key"]] = setting["value"]
		return settings

	def checkDB(self):
		refTables = {
			"chapter": {
				"series":     {"table":"series","col":"id"},
				"tgroup":     {"table":"tgroup","col":"id"},
				"source":     {"table":"series","col":"source"},
			},
		}
		tables = {
			"author": {
				"id":         {"pri":True,  "type":"varchar", "def":""},
				"name":       {"pri":False, "type":"varchar", "def":""},
				"favorite":   {"pri":False, "type":"boolean", "def":""},
				"ignore":     {"pri":False, "type":"boolean", "def":""},
				"deleted":    {"pri":False, "type":"boolean", "def":""},
				"source":     {"pri":True, "type":"boolean", "def":"mangadex"},
				"alt":        {"pri":False, "type":"boolean", "def":""},
				"altSorce":   {"pri":False, "type":"boolean", "def":""},
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
				"source":     {"pri":True, "type":"boolean", "def":"mangadex"},
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
				"source":     {"pri":True,  "type":"varchar", "def":"mangadex"},
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
				"source":     {"pri":True, "type":"boolean", "def":"mangadex"},
				"alt":        {"pri":False, "type":"boolean", "def":""},
				"altSorce":   {"pri":False, "type":"boolean", "def":""},
			},
			"locks": {
				"id":         {"pri":True,  "type":"varchar", "def":""},
				"pid":        {"pri":False, "type":"integer", "def":""},
				"timestamp":  {"pri":False, "type":"varchar", "def":""},
				"type":       {"pri":False, "type":"varchar", "def":""},
			},
		}
		settings = {
			"dbVersion":      {"name":"Database version (mikan.X)", "value":".".join(self.getInfo("version").split(".")[0:2])+".6", "user":"0", "possible":""},
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
			if os.path.isfile(self.getInfo("config")["db_location"]):
				db = sqlite3.connect(self.getInfo("config")["db_location"])
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
			self.logged(f"Database verify error: {e}")
			try:
				if self.getInfo("config")["db_auto_backup_update"].lower() == "true" and os.path.isfile(self.getInfo("config")["db_location"]) and os.access(os.path.dirname(self.getInfo("config")["db_location"]), os.W_OK):
					backupLoc = self.getInfo("config")["db_location"] + "_" + datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y%m%d%H%M%S') + ".bak"
					self.logged(f"Backing up database to {backupLoc}...")
					try:
						with open(self.getInfo("config")["db_location"], 'rb') as original_db:
							with open(backupLoc, 'wb') as backup_db:
								backup_db.write(original_db.read())
					except Exception as be:
						self.logged(traceback.format_exc())
						self.logged(f"Error during backup: {be}")
						self.logged(f"Cannot backup database, aborting update and exit...")
						sys.exit(1)
						return False
					self.logged("Backup completed")
				db = sqlite3.connect(self.getInfo("config")["db_location"])
				db.execute('PRAGMA journal_mode=WAL;')
				cursor = db.cursor()
				self.logged(f"Checking database from {self.getInfo("config")["db_location"]}...")
				for table in tables:
					self.logged(f"Checking table {table}...")
					cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(table,))
					result = cursor.fetchone()
					if result is None:
						self.logged(f"Creating {table} table...")
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
						if table in refTables:
							for col in refTables[table]:
								cursor.execute(f"PRAGMA foreign_key_list({table})")
								fkeys = cursor.fetchall()
								found = False
								for fk in fkeys:
									if fk[3] == col and fk[2] == refTables[table][col]["table"] and fk[4] == refTables[table][col]["col"]:
										found = True
										break
								if found == False:
									replace = True
									break
						if replace == True:
							self.logged(f"Needing to update table {table}...")
							for col in tbCols:
								if col not in tables[table]:
									self.logged(f"Cannot update table {table} automatically because {col} is no longer in new db version, need manual update, aborting...")
									raise Exception(f"Cannot update table {table} because {col} is no longer in new db version")
							self.logged(f"Renaming table {table} to {table}_old...")
							db.execute('PRAGMA foreign_keys=OFF;')
							cursor.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
							db.commit()
							self.logged(f"Creating new table {table}...")
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
							self.logged(f"Copying data from {table}_old to {table}...")
							mv = f"INSERT INTO {table} ({",".join(tbCols)}) SELECT {",".join(tbCols)} FROM {table}_old"
							cursor.execute(mv)
							db.commit()
							self.logged(f"Dropping old table {table}_old...")
							cursor.execute(f"DROP TABLE {table}_old")
							db.commit()
							db.execute('PRAGMA foreign_keys=ON;')
							db.commit()

				self.logged(f"Checking settings table...")
				cursor.execute("SELECT key FROM settings")
				avaliableSettings = [s[0] for s in cursor.fetchall()]
				for setting in settings:
					settingKey = setting
					settingName = settings[setting]["name"]
					settingValue = settings[setting]["value"]
					settingUser = settings[setting]["user"]
					settingPossible = settings[setting]["possible"]
					if setting not in avaliableSettings:
						self.logged(f"Add settings {setting}...")
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
				self.logged("Database checking completed")
			except (sqlite3.Error,Exception) as e:
				self.logged(traceback.format_exc())
				self.logged(f"Error: {e}")
				self.logged("Database checking failed, exiting...")
				sys.exit(1)
				return False
			return True

	def hashPassword(self, password):
		salt = os.urandom(16)
		pwdHash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
		return base64.b64encode(salt + pwdHash).decode('ascii')

	def verifyPassword(self, storedPWD, providePWD):
		storedPWD = base64.b64decode(storedPWD)
		salt = storedPWD[:16]
		storedPWDHash = storedPWD[16:]
		pwdhash = hashlib.pbkdf2_hmac('sha256', providePWD.encode('utf-8'), salt, 100000)
		return hmac.compare_digest(storedPWDHash, pwdhash)

	def setQueueStop(self,val:bool):
		with self.getInfo("queueStopLock"):
			self.setInfo("queueStopFlag",bool(val))
	def isQueueStop(self):
		with self.getInfo("queueStopLock"):
			return self.getInfo("queueStopFlag")

	def dbLock(self, lockID, lockType="queue"):
		try:
			db = sqlite3.connect(self.getInfo("config")["db_location"])
			cr = db.cursor()
			
			cr.execute("DELETE FROM locks WHERE timestamp < datetime('now', '-1 hour')")
			cr.execute("SELECT pid FROM locks WHERE id=? AND type=?", (lockID, lockType))
			
			row = cr.fetchone()
			if row:
				try:
					os.kill(row[0], 0)
					return False
				except OSError:
					cr.execute("DELETE FROM locks WHERE id=? AND type=?", (lockID, lockType))

			cr.execute("INSERT INTO locks (id, pid, timestamp, type) VALUES (?, ?, datetime('now'), ?)", (lockID, os.getpid(), lockType))
			db.commit()
			return True
		except sqlite3.Error:
			return False
		finally:
			db.close()
	def dbUnlock(self, lockID, lockType="queue"):
		try:
			db = sqlite3.connect(self.getInfo("config")["db_location"])
			cr = db.cursor()
			cr.execute("DELETE FROM locks WHERE id=? AND type=? AND pid=?", (lockID, lockType, os.getpid()))
			db.commit()
		except sqlite3.Error:
			return False
		finally:
			db.close()

class Process:
	def __init__(self, logged:Log|Callable|None=None) -> None:
		self.logged:Log|Callable = logged if logged != None or isinstance(logged,Log) or isinstance(logged,Callable) else Base().logged
		self.base:Base = Base(self.logged)
		self.progress:Progress = self.base.getInfo("progress")

	def addSerie(self, args:dict) -> dict:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		status=""
		self.logged(f"Adding: {args["id"]}")

		if args["provider"] in self.base.getInfo("provider"):
			mod = Modules(self.logged)
			mod.loadModule(args["provider"], logged=self.logged)
			dataSerie = mod.getSerieInfo(args["id"])
			mangadb = self.base.queryDB(select=["id"],table=["series"],where={"id":args["id"]})
			if len(mangadb) > 0 and args["id"] == mangadb[0]["id"]:
				status="Already added"
			else:
				self.base.insereplaceDB(table=["series"],values={"id":args["id"], "name":dataSerie["serie_original"], "forceName":dataSerie["serie_original"], "lastUpdate":dataSerie["lastUpdate"], "author":",".join(dataSerie["author"]), "artist":",".join(dataSerie["artist"]), "imageName":dataSerie["cover_id"], "image":dataSerie["cover"], "lastCheck":datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "favorite":"0", "fixedImage":"0", "priority":"0", "h":"0", "nameWarn":"0", "source":args["provider"]})
				status = f"Added: {dataSerie["serie_original"]}"

			thread=[]
			for a in dataSerie["author"] + dataSerie["artist"]:
				thread.append(threading.Thread(target=self.addAuthor,args=({"id":a,"provider":args["provider"]},)))
			for t in thread:
				t.start()
			for t in thread:
				t.join()
			status=f"Serie {dataSerie["serie_original"]} added"
		else:
			status = "Not valid id/provider"

		self.logged(status)
		return {"status":status}

	def addAuthor(self, args:dict) -> dict:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		status=""
		self.logged(f"Adding: {args["id"]}")

		authordb = self.base.queryDB(select=["id"],table=["author"],where={"id":args["id"]})
		if len(authordb) > 0 and args["id"] == authordb[0]["id"]:
			status=f"Already added: {args["id"]}"
		else:
			if args["provider"] in self.base.getInfo("provider"):
				mod = Modules(self.logged)
				mod.loadModule(args["provider"], logged=self.logged)
				author = mod.getAuthorInfo(args["id"])
				if author["status"] == 200:
					self.base.insereplaceDB(table=["author"],values={"id":author["id"], "name":author["name"], "favorite":"0"})
					status = f"Added: {args["id"]}"
				else:
					status = f"Failed to add: {args["id"]} ({author["status"]})"

		self.logged(status)
		return {"status":status}

	def addGroup(self, args:dict) -> dict:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		status=""
		self.logged(f"Adding: {args["id"]}")

		authordb = self.base.queryDB(select=["id"],table=["author"],where={"id":args["id"]})
		if len(authordb) > 0 and args["id"] == authordb[0]["id"]:
			status=f"Already added: {args["id"]}"
		else:
			if args["provider"] in self.base.getInfo("provider"):
				mod = Modules(self.logged)
				mod.loadModule(args["provider"], logged=self.logged)
				author = mod.getAuthorInfo(args["id"])
				if author["status"] == 200:
					self.base.insereplaceDB(table=["author"],values={"id":author["id"], "name":author["name"], "favorite":"0"})
					status = f"Added: {args["id"]}"
				else:
					status = f"Failed to add: {args["id"]} ({author["status"]})"

		self.logged(status)
		return {"status":status}

	def updateSerie(self, args:dict) -> dict:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		status=""
		self.logged(f"Updating: {args["id"]}")

		if args["provider"] in self.base.getInfo("provider"):
			manga = self.base.queryDB(select=["id"],table=["series"],where={"id":args["id"]})
			if len(manga) > 0 and args["id"] == manga[0]["id"]:
				mod = Modules(self.logged)
				mod.loadModule(args["provider"], logged=self.logged)
				dataSerie = mod.getSerieInfo(args["id"])

				self.base.updateDB(values={"name":dataSerie["serie_original"], "lastUpdate":dataSerie["lastUpdate"], "author":",".join(dataSerie["author"]), "artist":",".join(dataSerie["artist"]), "imageName":dataSerie["cover_id"], "image":dataSerie["cover"], "lastCheck":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, table=["series"], where={"id":args["id"],"source":args["provider"]})
				status = f"Updated: {dataSerie["serie_original"]}"

				thread=[]
				for a in dataSerie["author"] + dataSerie["artist"]:
					thread.append(threading.Thread(target=self.addAuthor,args=({"id":a,"provider":args["provider"]},)))
				for t in thread:
					t.start()
				for t in thread:
					t.join()
		else:
			status="Not valid id/provider"

		self.logged(status)
		return {"status":status}

	def downloadChapter(self, args:dict) -> dict:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"id", "type":str, "req":True},
				{"var":"serie", "type":str, "req":True},
				{"var":"provider", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		status=""

		chapterdbq = self.base.queryDB(select=["series","id","title","chapter","volume","tgroup","language","time","got"],table=["chapter"],where={"id":args["id"],"series":args["serie"]})
		seriedbq = self.base.queryDB(select=["id","name","forceName","author","artist","h","source"],table=["series"],where={"id":args["serie"],"source":args["provider"]})
		if len(chapterdbq) == 0: 
			status="Chapter not found in database"
			return {"status":status}
		if len(seriedbq) == 0:
			status="Serie not found in database"
			return {"status":status}
		chapterdb = chapterdbq[0]
		seriedb = seriedbq[0]
		if seriedb["source"] in self.base.getInfo("provider"):
			progressInfo = {
				"id": chapterdb["id"],
				"name": seriedb["name"] if seriedb["forceName"]==None or seriedb["forceName"]=="" else seriedb["forceName"],
				"parent": seriedb["id"],
				"provider": seriedb["source"],
				"type": "chapter",
				"status": "downloading",
				"statusText": f"getting chapter {chapterdb['title']} info",
				"progress": "0",
				"subprogress": "0"
			}
			self.progress.updatelist(progressInfo)
			settings = self.base.getInfo("settings")
			location = settings["saveHDir"] if seriedb["h"]==True else settings["saveDir"]
			format = settings["hSaveName"] if seriedb["h"]==True else settings["saveName"]
			author = [a["name"] for a in self.base.queryDB(select=["name"],table=["author"],where={"id":seriedb["author"].split(",")})] if seriedb["artist"] != "" else []
			artist = [a["name"] for a in self.base.queryDB(select=["name"],table=["author"],where={"id":seriedb["artist"].split(",")})] if seriedb["artist"] != "" else []
			chapter = {
				"provider": seriedb["source"],
				"serie_id": seriedb["id"],
				"provider": seriedb["source"],
				"author": ",".join(author),
				"artist": ",".join(artist),
				"group": ",".join(g["name"] for g in self.base.queryDB(select=["name"],table=["tgroup"],where={"id":chapterdb["tgroup"].split(",")},whereopt="or")) if chapterdb["tgroup"] != "" else "",
				"authors_artists": ",".join(author + artist),
				"serie_original": seriedb["name"],
				"serie_force": seriedb["forceName"] if seriedb["forceName"] != None else "",
				"serie": seriedb["name"] if seriedb["forceName"] == None or seriedb["forceName"] == "" else seriedb["forceName"],
				"serie_id": seriedb["id"] if seriedb["id"] != None else "",
				"volume": chapterdb["volume"] if chapterdb["volume"] != None else "0",
				"chapter": chapterdb["chapter"] if chapterdb["chapter"] != None else "0",
				"title": chapterdb["title"] if chapterdb["title"] != None else "",
				"lang_short": chapterdb["language"]
			}
			
			progressInfo.update({
				"statusText": f"downloading {chapter['title']} info",
				"progress": "20",
				"subprogress": "100"
			})
			self.progress.updatelist(progressInfo)
			mod = Modules(self.logged)
			mod.loadModule(args["provider"], logged=self.logged)
			img = mod.getChapterImg(args["id"])

			if len(img) == 0:
				progressInfo.update({
					"status": "failed",
					"statusText": f"failed to download {chapter['title']} (no data)",
					"progress": "100",
					"subprogress": "100"
				})
				self.progress.updatelist(progressInfo)
				status = f"failed to download {chapter['title']} (no data)"
				return {"status":status}

			imgLenth = len(img)
			imgPerPrecentFt = 1/imgLenth
			for image in img:
				progressInfo.update({
					"statusText": f"downloading chapter {chapter['title']} page {image["page"]}/{len(img)}",
					"progress": str(round(((image["page"]-1)/len(img))*80+20,2)),
					"subprogress": str(round(((image["page"]-1)/len(img))*100,2))
				})
				self.progress.updatelist(progressInfo)
				chapter["page"] = image["page"]
				chapter["extension"] = image["extension"]
				chapter["time"] = datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
				def percentCall(data):
					checkInput = self.base.checkArg({
						"input":args,
						"context":[{"var":"percent", "type":str, "req":True}]
					})
					if checkInput["status"]=="success":
						progressInfo.update({
							"subprogress": (image["page"]/len(img))*100 + checkInput["normal"]["percent"],
						})
						self.progress.updatelist(progressInfo)

				requestPage = self.base.downloadPage(url=image["url"], location=self.base.customFormat(location+format, **chapter), progressCallback=percentCall)
				if "callback" in image and isinstance(image["callback"],Callable):
					def run_callback():
						try:
							image["callback"](requestPage)
						except Exception as e:
							self.logged(f"Callback error: {e}")
					callbackThread = threading.Thread(target=run_callback, daemon=True)
					callbackThread.start()
					callbackThread.join(timeout=5)
					if callbackThread.is_alive():
						self.logged(f"Callback timeout after 5 seconds")
				if requestPage["status"] != 200:
					self.logged(f"Download {chapter['serie']} - chapter {chapter['chapter']} failed. (page:{image["page"]} url:{image["url"]})")
					progressInfo.update({
						"status": "failed",
						"statusText": f"download chapter {chapter['title']} failed (page:{image["page"]})",
						"progress": "100",
					})
					self.progress.updatelist(progressInfo)
					status = f"failed to download {chapter['title']} (not ok)"
					return {"status":status}
			self.base.updateDB(table=["chapter"], values={"got":1}, where={"id":chapterdb["id"]})
			self.logged(f"Download {chapter['serie']} - chapter {chapter['chapter']} success.")
			progressInfo.update({
				"status": "done",
				"statusText": f"download chapter {chapter['title']} success",
				"progress": "100",
				"subprogress": "100"
			})
			self.progress.updatelist(progressInfo)
			status = f"download chapter {chapter['title']} success"
		else:
			status = "Not valid provider"
		return {"status":status}

	def markGroupsProp(self, args:dict) -> dict:
		status=""
		checkInput = self.base.checkArg({
			"input":args,
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": status=checkInput["data"]["msg"];return {"status":status}
		info = checkInput["data"]["normal"]
		groupdb = self.base.queryDB(select=["id","ignore","fake","deleted"],table=["tgroup"],where={"id":args["id"]})
		if len(groupdb)>0 and groupdb[0]["id"]==args["id"]:
			checkInput = self.base.checkArg({
				"input":args,
				"context":[
					{"var":"ignore", "type":bool, "req":False, "def":groupdb[0]["ignore"]},
					{"var":"fake", "type":bool, "req":False, "def":groupdb[0]["fake"]},
					{"var":"deleted", "type":bool, "req":False, "def":groupdb[0]["deleted"]}
				]
			})
			if checkInput["status"]=="failed": status=checkInput["data"]["msg"];return
			args = checkInput["data"]["normal"]
			args.update(info)
			self.base.updateDB(values={"ignore":args["ignore"], "fake":args["fake"], "deleted":args["deleted"]}, table=["tgroup"], where={"id":args["id"]})
			status = "Saved"
		else:
			status = "No match group"
		return {"status":status}

	def markSerieProp(self, args:dict) -> dict:
		status=""
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"id", "type":str, "req":True},
				{"var":"provider", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": status=checkInput["data"]["msg"];return {"status":status}
		info = checkInput["data"]["normal"]
		seriedb = self.base.queryDB(select=["id","forceName","h","source"],table=["series"],where={"id":args["id"],"source":args["provider"]})
		if len(seriedb)>0 and seriedb[0]["id"]==args["id"] and seriedb[0]["source"]==args["provider"]:
			checkInput = self.base.checkArg({
				"input":args,
				"context":[
					{"var":"h", "type":bool, "req":False, "def":seriedb[0]["h"]},
					{"var":"forceName", "type":str, "req":False, "def":seriedb[0]["forceName"]}
				]
			})
			if checkInput["status"]=="failed": status=checkInput["data"]["msg"];return {"status":status}
			args = checkInput["data"]["normal"]
			args.update(info)
			self.base.updateDB(values={"h":args["h"],"forceName":args["forceName"] if args["forceName"]!="" else None}, table=["series"], where={"id":args["id"],"source":args["provider"]})
			status = "Saved"
		else:
			status = "No match serie"
		return {"status":status}

	def markChapterProp(self, args:dict) -> dict:
		status=""
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"id", "type":str, "req":True},
				{"var":"serie", "type":str, "req":True},
				{"var":"provider", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": status=checkInput["data"]["msg"];return {"status":status}
		info = checkInput["data"]["normal"]
		chapterdb = self.base.queryDB(select=["id","serie","source"],table=["chapter"],where={"id":args["id"],"series":args["serie"],"source":args["provider"]})
		if len(chapterdb)>0 and chapterdb[0]["id"]==args["id"] and chapterdb[0]["series"]==args["serie"] and chapterdb[0]["source"]==args["provider"]:
			checkInput = self.base.checkArg({
				"input":args,
				"context":[{"var":"get", "type":bool, "req":False, "def":chapterdb[0]["get"]}]
			})
			if checkInput["status"]=="failed": status=checkInput["data"]["msg"];return {"status":status}
			args = checkInput["data"]["normal"]
			args.update(info)
			self.base.updateDB(values={"get":args["get"]}, table=["chapter"], where={"id":args["id"],"series":args["serie"],"source":args["provider"]})
			status = "Saved"
		else:
			status = "No match chapter"
		return {"status":status}

	def updateCover(self, args:dict) -> dict:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]
		status = ""

		settings = self.base.getInfo("settings")
		seriedb = self.base.queryDB(select=["id","name","forceName","source","h"],table=["series"],where={"id":args["id"],"source":args["provider"]})
		if seriedb and args["id"] == seriedb[0]["id"] and seriedb[0]["source"] in self.base.getInfo("provider"):
			progressInfo = {
				"id": seriedb[0]["id"],
				"name": seriedb[0]["name"] if seriedb[0]["forceName"]==None or seriedb[0]["forceName"]=="" else seriedb[0]["forceName"],
				"parent": seriedb[0]["id"],
				"provider": seriedb[0]["source"],
				"type": "cover",
				"status": "downloading",
				"statusText": "downloading cover",
				"progress": "0",
				"subprogress": "0"
			}
			self.progress.updatelist(progressInfo)
			mod = Modules(self.logged)
			mod.loadModule(args["provider"], logged=self.logged)
			data = mod.getSerieInfo(args["id"])
			progressInfo.update({
				"statusText": "downloaded cover",
				"progress": "30",
				"subprogress": "100",
			})
			self.progress.updatelist(progressInfo)
			data["extension"] = data["cover_extension"]
			data["artist"] = data["artist_string"]
			data["author"] = data["author_string"]


			progressInfo.update({
				"status": "saving",
				"statusText": "saving cover to db",
				"progress": "40",
				"subprogress": "0",
			})
			self.progress.updatelist(progressInfo)
			self.base.updateDB(values={"imageName":data["cover_id"], "image":data["cover"]},table=["series"],where={"id":data["id"]})
			progressInfo.update({
				"status": "saving" if settings["saveCover"]=="yes" else "done",
				"statusText": "saved cover to db",
				"progress": "60" if settings["saveCover"]=="yes" else "100",
				"subprogress": "100",
			})
			self.progress.updatelist(progressInfo)

			if settings["saveCover"] == "yes":
				progressInfo.update({
					"statusText": "saving cover to file",
					"progress": "80",
					"subprogress": "0",
				})
				self.progress.updatelist(progressInfo)
				format = settings["coverDir"]
				lo = settings["saveDir"]

				if seriedb[0]["h"] == "1":
					format = settings["coverHDir"]
					lo = settings["saveHDir"]
				lo = self.base.customFormat(lo+format, **data)
				
				os.makedirs(os.path.dirname(lo),exist_ok=True)
				with open(lo, "wb") as file:
					file.write(data["cover"])
				self.logged(f"Cover saved as {lo}")
				progressInfo.update({
					"status": "done",
					"statusText": "saved cover to file",
					"progress": "100",
					"subprogress": "100",
				})
				self.progress.updatelist(progressInfo)
		else:
			self.logged("Not valid id/provider")
			status = "Not valid id/provider"
		return {"status":status}

	def getChapterList(self,args):
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True},
				{"var":"toqueue", "type":str, "def":self.base.getInfo("settings")["AutoQueue"]}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]
		natsort = lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s or '')]
		settings = self.base.getInfo("settings")
		status = ""

		seriedb = self.base.queryDB(select=["id","name","forceName","h","source"],table=["series"],where={"id":args["id"],"source":args["provider"]})
		if len(seriedb) < 1 or args["id"] != seriedb[0]["id"] or args["provider"] not in self.base.getInfo("provider"):
			status = "Not valid id/provider or not added"
			self.logged("Not valid id/provider or not added")
			return {"status":status}

		progressInfo = {
			"id": args["id"],
			"name": seriedb[0]["name"] if seriedb[0]["forceName"]==None or seriedb[0]["forceName"]=="" else seriedb[0]["forceName"],
			"parent": seriedb[0]["id"],
			"provider": seriedb[0]["source"],
			"type": "info",
			"status": "downloading",
			"statusText": "getting serie info",
			"progress": "0",
			"subprogress": "100"
		}
		self.progress.updatelist(progressInfo)
		igGroup = {g["id"] for g in self.base.queryDB(select=["id"],table=["tgroup"],where={"ignore":"1"})}
		fkGroup = {g["id"] for g in self.base.queryDB(select=["id"],table=["tgroup"],where={"fake":"1"})}
		location = settings["saveHDir"] if seriedb[0]["h"] else settings["saveDir"]
		format = settings["hSaveName"] if seriedb[0]["h"] else settings["saveName"]
		mod = Modules(logged=self.logged)
		mod.loadModule(args["provider"])
		dataSerie = mod.getSerieInfo(args["id"])
		manga = []
		mangaVol = {}
		progressInfo.update({
			"name": dataSerie["serie"],
			"subprogress": "100",
			"progress": "20",
			"statusText": "getting chapter list",
		})
		self.progress.updatelist(progressInfo)
		allChapter = mod.getChapterList(args["id"])

		for i,chp in enumerate(allChapter, start=1):
			progressInfo.update({
				"statusText": f"parsing chapter info ({i+1}/{len(allChapter)})",
				"subprogress": str(round((i/len(allChapter))*100,2)),
				"progress": str(round(((i/len(allChapter))*40)+60,2)),
			})
			self.progress.updatelist(progressInfo)
			data = {}
			data["id"] = chp["id"]
			data["serie_id"] = dataSerie["id"]
			data["serie"] = dataSerie["serie"]
			data["volume"] = chp["volume"]
			data["chapter"] = chp["chapter"]
			data["title"] = chp["title"]
			data["lang_short"] = chp["lang_short"]
			data["group"] = chp["group"]
			data["groupid"] = chp["groupid"]

			group = chp["group_combid"]
			groupDB = [gdb["id"] for gdb in self.base.queryDB(select=["id"],table=["tgroup"],where={"id":[g["id"] for g in group]},whereopt="or")]
			for g in group:
				if g["id"] not in groupDB:
					self.base.insereplaceDB(table=["tgroup"],values={"id":g["id"], "name":g["name"], "ignore":"0", "fake":g["fake"], "deleted":"0"})
					fkGroup.add(g["id"]) if g["fake"] == "1" else None
			if not set(data["groupid"].split(",")).isdisjoint(igGroup):
				self.logged(f"Ignore chapter {data["chapter"]} from {data["group"]} (ignore)")
				continue
			if settings["ignoreFake"] == "yes" and not set(data["groupid"].split(",")).isdisjoint(fkGroup):
				self.logged(f"Ignore chapter {data["chapter"]} from {data["group"]} (fake/official)")
				continue
			r = location + format
			if data["volume"] not in mangaVol:
				mangaVol[data["volume"]] = []
			mangaVol[data["volume"]].append({"path":r,"data":data})

		mangaVol = dict(sorted(mangaVol.items(), key=lambda item: (item[0] is None, natsort(item[0] or ''))))
		for k,v in mangaVol.items():
			mangaVol[k] = sorted(v, key=lambda x: natsort(x["data"]["chapter"]))
			for p in mangaVol[k]:
				chp = self.base.queryDB(select=["id","got"],table=["chapter"],where={"id":p["data"]["id"]})
				if len(chp) > 0 and p["data"]["id"] == chp[0]["id"] and chp[0]["got"] == True:
					p["data"]["downloaded"] = True
				elif len(chp) > 0 and p["data"]["id"] == chp[0]["id"] and chp[0]["got"] == False:
					p["data"]["downloaded"] = False
					if args["toqueue"] == "yes":
						progressInfoChapter = progressInfo.copy()
						progressInfoChapter.update({
							"id": p["data"]["id"],
							"type": "chapter",
							"status": "pending",
							"statusText": f"pending to download chapter {p["data"]["chapter"]}",
							"subprogress": "0",
							"progress": "0",
						})
						self.progress.updatelist(progressInfoChapter)
				else:
					p["data"]["downloaded"] = False
					self.base.insereplaceDB(table=["chapter"], values={"id":p["data"]["id"], "series":dataSerie["id"], "title":p["data"]["title"] if p["data"]["title"] is not None else "", "volume":p["data"]["volume"] if p["data"]["volume"] is not None else "", "chapter":p["data"]["chapter"], "tgroup":p["data"]["groupid"] if "groupid" in p["data"] else "", "language":p["data"]["lang_short"], "time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "got":"0"})
					if args["toqueue"] == "yes":
						progressInfoChapter = progressInfo.copy()
						progressInfoChapter.update({
							"id": p["data"]["id"],
							"type": "chapter",
							"status": "pending",
							"statusText": f"pending to download chapter {p["data"]["chapter"]}",
							"subprogress": "0",
							"progress": "0",
						})
						self.progress.updatelist(progressInfoChapter)
				manga.append(p)
		progressInfo.update({
			"status": "done",
			"statusText": "get all chapter info success",
			"subprogress": "100",
			"progress": "100",
		})
		self.progress.updatelist(progressInfo)
		status = "get all chapter info success"
		return {"status":status}

	def setSettings(self,value):
		settingsList = json.loads(value)
		for setting in settingsList:
			self.base.updateDB(table=["settings"], values={"value":setting["value"]}, where={"key":setting["id"]})
		self.base.initInfo(["settings"],True)

		return {"status":"Saved settings"}

	def downloadAllChapter(self,args):
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args = checkInput["data"]["normal"]
		status = ""

		mangadb = self.base.queryDB(select=["id","title","got"],table=["chapter"],where={"series":args["id"]})
		seriedb = self.base.queryDB(select=["id","name","forceName","source","h"],table=["series"],where={"id":args["id"],"source":args["provider"]})
		if len(seriedb) > 0:
			for manga in mangadb:
				if manga["got"] == False:
					progressInfo = {
						"id": args["id"],
						"name": seriedb[0]["name"] if seriedb[0]["forceName"]==None or seriedb[0]["forceName"]=="" else seriedb[0]["forceName"],
						"parent": seriedb[0]["id"],
						"provider": seriedb[0]["source"],
						"type": "download",
						"status": "pending",
						"statusText": f"pending to download chapter {manga["title"]}",
						"progress": "0",
						"subprogress": "0"
					}
					self.progress.updatelist(progressInfo)
			self.base.processQueue()

			return {"status":status}
		else:
			status = "Not valid id/provider"
			self.logged("Not valid id/provider")
			return {"status":status}

	def getAllSeriesChapter(self):
		series = self.base.queryDB(select=["id","name","source"],table=["series"])
		for s in series:
			if s["source"] in self.base.getInfo("provider"):
				self.getChapterList({"id":s["id"],"provider":s["source"]})
		return {"status":"check all series chapters completed"}

	def clearCache(self):
		self.logged("Clearing request cache")
		self.base.requestGet.cache_clear()
		return {"status":"Cleared request cache"}

	def clearQueue(self):
		self.logged("Clearing queue")
		progres:Progress = self.base.getInfo("progress")
		progres.clear()
		self.base.deleteDB(table=["queue"],where={"status":["pending","downloading","done"]},whereopt="or")
		return {"status":"Cleared queue"}

	def clearDoneQueue(self):
		self.logged("Clearing done queue")
		progres:Progress = self.base.getInfo("progress")
		progres.clearDone()
		self.base.deleteDB(table=["queue"],where={"status":"done"})
		return {"status":"Cleared done queue"}

	def processQueue(self,failed=False):
		if not self.base.dbLock("queueprocess") or self.base.getInfo("runningQueue"):
			self.logged("Queue process already running in another instance, skipping...")
			return {"status":"Queue process already running in another instance"}
		self.base.setQueueStop(False)

		def heartbeat():
			import time
			while self.base.getInfo("runningQueue"):
				self.base.updateDB(values={"timestamp":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, table=["locks"], where={"id":"queueprocess", "type":"queue", "pid":os.getpid()})
				time.sleep(300)

		try:
			self.base.setInfo("runningQueue", True)
			hbt = threading.Thread(target=heartbeat, daemon=True)
			hbt.start()
			self.logged("Starting queue process...")
			qAll = False
			queued = self.base.queryDB(select=["id","parent","type","status","statusText","source"],table=["queue"], where={"status":"pending" if not failed else "failed"})

			while qAll != True:
				for q in queued:
					if self.base.isQueueStop():
						self.logged("Queue process stopped by external signal")
						qAll = True
						break

					if q["type"] == "chapter":
						self.downloadChapter({"id":q["id"], "serie":q["parent"], "provider":q["source"]})
					elif q["type"] == "serieinfo":
						self.updateSerie({"id":q["id"], "provider":q["source"]})
					elif q["type"] == "cover":
						self.updateCover({"id":q["id"], "provider":q["source"]})

				queued = self.base.queryDB(select=["id","parent","type","status","statusText","source"],table=["queue"], where={"status":"pending" if not failed else "failed"})
				if len(queued)<1:
					qAll = True
		except Exception as e:
			self.logged(f"Error processing queue: {str(e)}")
			return {"status":f"Error processing queue: {str(e)}"}
		finally:
			self.base.setInfo("runningQueue", False)
			self.base.setQueueStop(False)
			self.base.dbUnlock("queueprocess")
			self.logged("Queue process complete")
			return {"status":"Queue process complete"}

class View:
	def __init__(self, logged:Callable=None) -> None:
		self.logged = logged if logged != None else Base().logged
		self.base = Base(self.logged)

	def knownSeries(self) -> list:
		out = []
		seriedb = self.base.queryDB(select=["id","name","forceName","h","source","author","artist"],table=["series"],where=({} if Base().getInfo("settings")["showH"] == "yes" else {"h":False}))
		a = set()
		for s in seriedb:
			a.update(re.sub(r"\s*,+\s*$", "", re.sub(r"\s*,+\s*", ",", s["author"]+","+s["artist"])).split(","))
		authordb = self.base.queryDB(select=["id","name"],table=["author"],where={"id":list(a)},whereopt="or")
		author = {a["id"]: a["name"] for a in authordb}
		for s in seriedb:
			out.append({
				"serieid": s["id"],
				"name": s["forceName"] if s["forceName"] != None and s["forceName"] != "" else s["name"],
				"authors": ", ".join([author[a] if a in author else "Unknown" for a in re.sub(r"\s*,+\s*$", "", re.sub(r"\s*,+\s*", ",", s["author"])).split(",")]),
				"artists": ", ".join([author[a] if a in author else "Unknown" for a in re.sub(r"\s*,+\s*$", "", re.sub(r"\s*,+\s*", ",", s["artist"])).split(",")]),
				"h": s["h"],
				"provider": s["source"]
			})
		return out

	def knownSeriesChapter(self, args:dict) -> list:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		out = []
		for d in self.base.queryDB(select=["chapter.series AS serieid", "chapter.id AS chapterid", "chapter.title AS name", "chapter.chapter AS chapter", "chapter.volume AS volume", "chapter.got AS dl", "chapter.tgroup AS tgroupid", "tgroup.name AS tgroup", "chapter.time AS time"], table=["chapter LEFT JOIN tgroup ON chapter.tgroup = tgroup.id"], where={"series": args["id"]}):
			out.append({"serieid": d["serieid"], "chapterid": d["chapterid"], "name": d["name"], "chapter": d["chapter"], "volume": d["volume"], "saved": "true" if d["dl"]==1 else "false" , "tgroupid": d["tgroupid"], "tgroup": d["tgroup"] if d["tgroup"]!=None else "", "check": d["time"]})
		return out

	def knownGroups(self) -> list:
		out = []
		for data in self.base.queryDB(select=["id","name","ignore","fake","deleted"],table=["tgroup"]):
			out.append({"tgroupid": data["id"], "name": data["name"], "ignore": data["ignore"] if data["ignore"] == 1 else 0, "fake": data["fake"] if data["fake"] == 1 else 0, "deleted": data["deleted"] if data["deleted"] == 1 else 0})
		return out

	def getCover(self, args:dict) -> bytes:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":False, "def":False},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		data = self.base.queryDB(select=["image"],table=["series"],where={"id":args["id"]})
		if data:
			return data[0]["image"]
		elif args["provider"] in self.base.getInfo("provider"):
			mod = Modules(self.logged)
			mod.loadModule(args["provider"], logged=self.logged)
			return mod.getCover(args["id"])
		else:
			return self.getAppBG({"color":"#000000","type":"color"})

	def getAppBG(self, args:dict={}) -> bytes:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"id", "type":str, "req":False, "def":None},
				{"var":"color", "type":str, "req":False, "def":None},
				{"var":"type", "type":str, "req":False, "def":None}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		settings = self.base.getInfo("settings")
		color = (0,0,0)
		if isinstance(args["color"],str) and args["color"].startswith("#") and len(args["color"])==6:
			color = tuple(int(args["color"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
		elif isinstance(settings["appBGColor"],str) and settings["appBGColor"].startswith("#") and len(settings["appBGColor"])==6:
			color = tuple(int(settings["appBGColor"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
		seriedb = self.base.queryDB(select=["id","source"],table=["series"],where={"id":settings["appBGCover"]})
		seriedba = self.base.queryDB(select=["id","source"],table=["series"],where={"id":args["id"]})
		rtype = args["type"] if args["type"]=="cover" or args["type"]=="color" else settings["appBGType"]
		if rtype == "cover":
			if seriedba and args["id"] == seriedba[0]["id"]:
				return self.getCover({"id":seriedba[0]["id"],"provider":seriedba[0]["source"]})
			elif seriedb and settings["appBGCover"] == seriedb[0]["id"]:
				return self.getCover({"id":seriedb[0]["id"],"provider":seriedb[0]["source"]})
		elif rtype == "color":
			import zlib, struct
			ihdr = b'IHDR' + struct.pack('!IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
			ihdr = struct.pack('!I', len(ihdr) - 4) + ihdr + struct.pack('!I', zlib.crc32(ihdr) & 0xffffffff)
			raw = b'\x00' + bytes(color)
			comp = zlib.compress(raw)
			idat = b'IDAT' + comp
			idat = struct.pack('!I', len(comp)) + idat + struct.pack('!I', zlib.crc32(idat) & 0xffffffff)
			iend = struct.pack('!I', 0) + b'IEND' + struct.pack('!I', zlib.crc32(b'IEND') & 0xffffffff)
			return b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend

	def searchSerie(self, args:dict) -> list:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"value", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]
		if args["provider"] in self.base.getInfo("provider"):
			mod = Modules(self.logged)
			mod.loadModule(args["provider"], logged=self.logged)
			return mod.search(args["value"])
		else:
			self.logged("cannot search serie: invalid provider")
			return []

	def getSerieInfo(self, args:dict) -> list:
		checkInput = self.base.checkArg({
			"input":args,
			"context":[
				{"var":"provider", "type":str, "req":True},
				{"var":"id", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]
		if args["provider"] in self.base.getInfo("provider"):
			mod = Modules(self.logged)
			mod.loadModule(args["provider"], logged=self.logged)
			return mod.getSerieInfo(args["value"])
		else:
			self.logged("cannot search serie: invalid provider")
			return []

	def getSettings(self) -> list:
		data = self.base.queryDB(select=["key","name","value"],table=["settings"],where={"user":"1"})
		re = []
		for d in data:
			re.append({"id": d["key"], "name": d["name"], "value": d["value"]})
		return re