import configparser
import datetime
import os
import pprint
import re
import sys
import time
import requests
import json
import sqlite3
import threading

scriptLocation = os.path.abspath(os.path.dirname(sys.argv[0]))
searchParam = "includes[]=cover_art,author"+"&"+"order[relevance]=desc"+"&"+"originalLanguage[]=ja"+"&"+"contentRating[]=safe"+"&"+"contentRating[]=suggestive"+"&"+"contentRating[]=erotica"+"&"+"contentRating[]=pornographic"
md = "https://www.mangadex.org"
apiUrl = "https://api.mangadex.org"
imageUrl = "https://uploads.mangadex.org"
arg = sys.argv

def readConfig():
	conf = {}
	config = configparser.ConfigParser(interpolation=None)
	config.read(scriptLocation+'/config.ini')
	if ('main' in config) == False:
		config['main'] = {}

	conf["ssl_crt_location"] = config.get('main','ssl_crt_location',fallback="''").replace("'","")
	conf["ssl_key_location"] = config.get('main','ssl_key_location',fallback="''").replace("'","")
	conf["port"] = config.get('main','port',fallback="'8089'").replace("'","")
	conf["host"] = config.get('main','host',fallback="''").replace("'","")
	conf["secret"] = config.get('main','secret',fallback="'false'").replace("'","")
	conf["token_valid_time"] = config.get('main','token_valid_time',fallback="'86400'").replace("'","")
	conf["db_location"] = config.get('main','db_location',fallback="'./mikan.db'").replace("'","")
	config['main']['ssl_crt_location'] = "'"+conf["ssl_crt_location"]+"'"
	config['main']['ssl_key_location'] = "'"+conf["ssl_key_location"]+"'"
	config['main']['port'] = "'"+conf["port"]+"'"
	config['main']['host'] = "'"+conf["host"]+"'"
	config['main']['secret'] = "'"+conf["secret"]+"'"
	config['main']['token_valid_time'] = "'"+conf["token_valid_time"]+"'"
	config['main']['db_location'] = "'"+conf["db_location"]+"'"

	with open(scriptLocation+'/config.ini', 'w') as configfile:
		config.write(configfile)
	for key in conf.keys():
		if conf[key].startswith("./"):
			conf[key] = conf[key].replace("./",scriptLocation+"/",1)
	return conf

config = readConfig()

class RunOtherMeta(type):
	def __new__(cls, name, bases, attrs):
		for key, value in attrs.items():
			if callable(value):
				def wrapper(func):
					def wrapped(*args, **kwargs):
						z="zero0200"
						return func(*args, **kwargs)
					return wrapped

				attrs[key] = wrapper(value)

		return super().__new__(cls, name, bases, attrs)

class MDMain(metaclass=RunOtherMeta):
	def search(self,searchV):
		r = requests.get(f"{apiUrl}/manga?{searchParam}", params={"title": searchV})
		data = r.json()["data"]
		self.logged(f"{apiUrl}/manga?{searchParam}&title={searchV}")
		re = []
		for d in data:
			data = {"serieid": d["id"], "name": "", "authorid": "", "author": "", "artistid": "", "artist": ""}
			for t in d["attributes"]["title"]:
				data["name"] = d["attributes"]["title"][t]
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			for a in d["relationships"]:
				if a["type"] == "author":
					cursor = db.cursor()
					cursor.execute("SELECT COALESCE((SELECT name FROM author WHERE id = ?), 'Unknown')", (a["id"],))
					name = cursor.fetchone()
					cursor.close()
					data["authorid"] = data["authorid"]+a["id"]+", "
					data["author"] = data["author"]+name[0]+", "
				if a["type"] == "artist":
					cursor = db.cursor()
					cursor.execute("SELECT COALESCE((SELECT name FROM author WHERE id = ?), 'Unknown')", (a["id"],))
					name = cursor.fetchone()
					cursor.close()
					data["artistid"] = data["artistid"]+a["id"]+", "
					data["artist"] = data["artist"]+name[0]+", "
			data["author"] = data["author"].rstrip(", ")
			data["authorid"] = data["authorid"].rstrip(", ")
			data["artist"] = data["artist"].rstrip(", ")
			data["artistid"] = data["artistid"].rstrip(", ")
			db.close()

			re.append(data)

		return re

	def searchChapter(self,searchV):
		r = requests.get(f"{apiUrl}/manga/{searchV}/feed")
		self.logged(f"{apiUrl}/manga/{searchV}/feed")
		data = r.json()["data"]
		re = []
		for d in data:
			data = {"serieid": d["id"], "chapter": d["attributes"]["chapter"], "volume": d["attributes"]["volume"], "name": d["attributes"]["title"], "tgroupid": "", "tgroup": "", "language": d["attributes"]["translatedLanguage"], "time": ""}
			db = sqlite3.connect(config["db_location"])
			for a in d["relationships"]:
				if a["type"] == "scanlation_group":
					cursor = db.cursor()
					cursor.execute("SELECT COALESCE((SELECT name FROM tgroup WHERE id = ?), 'Unknown')", (a["id"],))
					name = cursor.fetchone()
					cursor.close()
					data["tgroupid"] = data["tgroupid"]+a["id"]+", "
					data["tgroup"] = data["tgroup"]+name[0]+", "
			data["tgroup"] = data["tgroup"].rstrip(", ")
			data["tgroupid"] = data["tgroupid"].rstrip(", ")
			data["tgroup"] = data["tgroup"].rstrip(", ")
			data["tgroupid"] = data["tgroupid"].rstrip(", ")
			db.close()

			re.append(data)
		re=sorted(re, key=lambda x: (float((x["volume"]) if x["volume"] is not None else -1), float(x["chapter"]) if x["chapter"] is not None else 0))

		return re

	def knownSeriesChapter(self,serieid):
		db = sqlite3.connect(config["db_location"])
		cursor = db.cursor()
		cursor.execute("SELECT chapter.series, chapter.id, chapter.title, chapter.chapter, chapter.volume, chapter.tgroup, tgroup.name, chapter.time FROM chapter LEFT JOIN tgroup ON chapter.tgroup = tgroup.id WHERE series = ?", (serieid,))
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			serieid, chapterid, name, chapter, volume, tgroupid, tgroup, time = d
			re.append({"serieid": serieid, "chapterid": chapterid, "name": name, "chapter": chapter, "volume": volume, "tgroupid": tgroupid, "tgroup": tgroup, "check": time})

		return re

	def knownSeries(self):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("""
			SELECT s.id AS serieid, s.name AS name,
				GROUP_CONCAT(DISTINCT COALESCE(a1.name, 'Unknown')) AS authors,
				GROUP_CONCAT(DISTINCT COALESCE(a2.name, 'Unknown')) AS artists
			FROM series s
			LEFT JOIN author a1 ON ',' || s.author || ',' LIKE '%,' || a1.id || ',%'
			LEFT JOIN author a2 ON ',' || s.artist || ',' LIKE '%,' || a2.id || ',%'
			GROUP BY s.id, s.name
			ORDER BY s.id ASC
		""")
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			serieid, name, author_names, artist_names = d
			re.append({"serieid": serieid, "name": name, "authors": author_names.replace(",",", "), "artists": artist_names.replace(",",", ")})

		return re

	def knownSeriesData(self,id,col):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("SELECT id,name FROM series")
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			re.append({"serieid": d[0], "name": d[1]})

		return re

	def setSetting(self,id,value):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("SELECT id,name FROM series")
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			re.append({"serieid": d[0], "name": d[1]})

		return re

	def setSettings(self,value):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		settingsList = json.loads(value)
		for setting in settingsList:
			cursor.execute("UPDATE `settings` SET `value` = ? WHERE key = ?", (setting["value"],setting["id"],))

		db.commit()
		cursor.close()
		db.close()

		return {"status":"Saved settings"}

	def getSettings(self):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("SELECT key,name,value FROM settings WHERE user = 1;")
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			id, name, value = d
			re.append({"id": id, "name": name, "value": value})

		return re

	def addSerie(self,id):
		status=""
		self.logged(f"Adding: {id}")

		if id != "":
			dataSerie = self.getSerieInfo(id)
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id FROM series WHERE id = ?", (id,))
			name = cursor.fetchone()
			cursor.close()
			if name != None and id == name[0]:
				status="Already added"
			else:
				cursor = db.cursor()
				cursor.execute("INSERT OR REPLACE INTO `series` (`id`,`name`,`lastUpdate`, `author`, `artist`, `imageName`, `image`, `lastCheck`, `favorite`, `fixedImage`, `priority`, `h`, `nameWarn`) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0)", (id, dataSerie["serie_original"], dataSerie["lastUpdate"],",".join(dataSerie["author"]) ,",".join(dataSerie["artist"]) ,dataSerie["cover_id"] ,dataSerie["cover"] , datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),)
				db.commit()
				cursor.close()
				status = f"Added: {dataSerie["serie_original"]}"

			db.close()
			thread=[]
			for a in dataSerie["author"] + dataSerie["artist"]:
				thread.append(threading.Thread(target=self.addAuthor,args=(a,)))
			for t in thread:
				t.start()
			for t in thread:
				t.join()

		else:
			status = "No id query"

		self.logged(status)
		return {"status":status}

	def updateSerie(self,id):
		status=""
		self.logged(f"Updating: {id}")

		if id != "":
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id FROM series WHERE id = ?", (id,))
			name = cursor.fetchone()
			cursor.close()
			if name != None and id == name[0]:
				dataSerie = self.getSerieInfo(id)

				cursor = db.cursor()
				cursor.execute("UPDATE `series` SET `name` = ?, `lastUpdate` = ?, `author` = ?, `author` = ?, `imageName` = ?, `image` = ?, `lastCheck` = ? WHERE id = ?", (dataSerie["serie_original"], dataSerie["lastUpdate"], ",".join(dataSerie["author"]), ",".join(dataSerie["artist"]), dataSerie["cover_id"], dataSerie["cover"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),id,))
				db.commit()
				cursor.close()
				status = f"Updated: {dataSerie["serie_original"]}"

				db.close()
				thread=[]
				for a in dataSerie["author"] + dataSerie["artist"]:
					thread.append(threading.Thread(target=self.addAuthor,args=(a,)))
				for t in thread:
					t.start()
				for t in thread:
					t.join()
			else:
				status="Not valid id"
		else:
			status = "No id query"

		self.logged(status)
		return {"status":status}

	def addAuthor(self,id):
		status=""
		self.logged(f"Adding: {id}")

		if id != "":
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id FROM author WHERE id = ?", (id,))
			name = cursor.fetchone()
			cursor.close()
			if name != None and id == name[0]:
				status="Already added"
			else:
				r = requests.get(f"{apiUrl}/author/{id}")
				self.logged(f"{apiUrl}/author/{id}")
				author = r.json()["data"]

				cursor = db.cursor()
				cursor.execute("INSERT OR REPLACE INTO `author` (`id`,`name`,`favorite`) VALUES (?, ?, 0)", (id,author["attributes"]["name"],))
				db.commit()
				cursor.close()
				status = f"Added: {author["attributes"]["name"]}"
			db.close()
		else:
			status = "No id query"

		self.logged(status)
		return {"status":status}

	def formatToReal(self,data,format):
		# for ref only
		data["series"] = data.get('series',"") #w
		data["group"] = data.get('group',"") #w
		data["authors_artists"] = data.get('authors_artists',"") #w
		data["volume"] = data.get('volume',"0") #w
		data["chapter"] = data.get('chapter',"0") #w
		data["title"] = data.get('title',"") #w
		data["page"] = data.get('page',"") #w
		data["extension"] = data.get('extension',"") #w
		data["lang_full"] = data.get('lang_full',"")
		data["lang_short"] = data.get('lang_short',"") #w
		data["date"] = data.get('date',"")
		data["time"] = data.get('time',"")
		data["h_series"] = data.get('H',"")

		return format % data

	def custom_format(self, format, **data):
		modified_data = {}
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

				modified_data[key] = value

		return format.format(**modified_data)

	def downloadToLestest(self,id):
		if id != "":
			dataSerie = self.getSerieInfo(id)
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id,name FROM series WHERE id = ?", (id,))
			name = cursor.fetchone()
			if name != None and id == name[0]:
				manga = []
				mangaVol = {}
				natsort = lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s or '')]
				cursor.execute("SELECT value FROM settings WHERE key = 'saveDir'")
				location = cursor.fetchone()[0]
				cursor.execute("SELECT value FROM settings WHERE key = 'saveName'")
				format = cursor.fetchone()[0]
				cursor.execute("SELECT value FROM settings WHERE key = 'languages'")
				lang = cursor.fetchone()[0].split(",")
				cursor.close()
				allChapter = []
				alchp = False
				alchplimit = 100
				alchpoffset = 0
				while alchp == False:
					r = requests.get(f"{apiUrl}/manga/{id}/feed?limit={alchplimit}&offset={alchpoffset}&includes[]=scanlation_group&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=safe&contentRating[]=erotica&contentRating[]=pornographic")
					self.logged(f"{apiUrl}/manga/{id}/feed?limit={alchplimit}&offset={alchpoffset}&includes[]=scanlation_group&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=safe&contentRating[]=erotica&contentRating[]=pornographic")
					chp = r.json()
					allChapter.extend(chp["data"])
					if len(allChapter) == chp["total"]:
						alchp = True
					else:
						alchpoffset=alchplimit+alchpoffset
					time.sleep(1)

				for chp in allChapter:
					if chp["attributes"]["translatedLanguage"] in lang:
						data = {}
						data["id"] = chp["id"]
						data["serie"] = dataSerie["serie"]
						data["volume"] = chp["attributes"]["volume"]
						data["chapter"] = chp["attributes"]["chapter"]
						data["title"] = chp["attributes"]["title"]
						data["lang_short"] = chp["attributes"]["translatedLanguage"]
						for chpRel in chp["relationships"]:
							if chpRel["type"] == "scanlation_group":
								cursor = db.cursor()
								cursor.execute("SELECT id FROM tgroup WHERE id = ?", (chpRel["id"],))
								tg = cursor.fetchone()
								if tg != None and chpRel["id"] == tg[0]:
									data["group"] = chpRel["attributes"]["name"]
									data["groupid"] = chpRel["id"]
								else:
									cursor.execute("INSERT INTO `tgroup` (`id`,`name`,`ignore`,`fake`,`deleted`) VALUES (?, ?, 0, 0, 0)", (chpRel["id"],chpRel["attributes"]["name"],))
									db.commit()
									data["group"] = chpRel["attributes"]["name"]
									data["groupid"] = chpRel["id"]
								cursor.close()
						r=location+format
						if data["volume"] in mangaVol:
							mangaVol[data["volume"]].append({"path":r,"data":data})
						else:
							mangaVol[data["volume"]] = []
							mangaVol[data["volume"]].append({"path":r,"data":data})

				mangaVol = dict(sorted(mangaVol.items(), key=lambda item: (item[0] is None, natsort(item[0] or ''))))
				for k,v in mangaVol.items():
					mangaVol[k] = sorted(v, key=lambda x: natsort(x["data"]["chapter"]))
					for p in mangaVol[k]:
						cursor = db.cursor()
						cursor.execute("SELECT id,got FROM chapter WHERE id = ? ", (p["data"]["id"],))
						chp = cursor.fetchone()
						cursor.close()
						if chp != None and p["data"]["id"] == chp[0] and chp[1] == True:
							p["data"]["downloaded"]=True
							p["data"]["db"]=True
						elif chp != None and p["data"]["id"] == chp[0] and chp[1] == True:
							p["data"]["downloaded"]=True
							p["data"]["db"]=True
						elif chp != None and p["data"]["id"] == chp[0] and chp[1] == False:
							p["data"]["downloaded"]=False
							p["data"]["db"]=True
						else:
							p["data"]["downloaded"]=False
							p["data"]["db"]=False
						""" p["data"]["downloaded"]=False
						p["data"]["db"]=False """
						manga.append(p)

				for v in manga:
					if v["data"]["downloaded"] == False:
						r = requests.get(f"{apiUrl}/at-home/server/{v["data"]["id"]}")
						self.logged(f"{apiUrl}/at-home/server/{v["data"]["id"]}")
						chp = r.json()

						for i,p in enumerate(chp["chapter"]["data"], start=1): 
							r = requests.get(f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}")
							self.logged(f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}")
							content = r.content
							report = {
								"url": f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}",
								"success": False,
								"bytes": len(content),
								"duration": round(r.elapsed.total_seconds() * 1000),
								"cached": False
							}
							v["data"]["page"] = str(i)
							v["data"]["extension"] = os.path.splitext(p)[1]
							v["data"]["time"] = datetime.datetime.fromisoformat(datetime.datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
							d = v["data"]
							if r.status_code == 200:
								report["success"] = True
								report["cached"] = True
								self.logged(report)
								lo = self.custom_format(v["path"], **d)
								os.makedirs(os.path.dirname(lo),exist_ok=True)
								with open(lo, "wb") as file:
									file.write(content)
								self.logged(f"Image saved as {lo}")
							else:
								self.logged("Failed to download image. Status code:", r.status_code)
							r = requests.post("https://api.mangadex.network/report",json=report)
					if v["data"]["db"] == False:
						cursor = db.cursor()
						cursor.execute("INSERT OR REPLACE INTO `chapter` (`id`,`series`,`title`,`volume`,`chapter`,`tgroup`,`language`,`time`,`got`) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)", (v["data"]["id"],name[0],v["data"]["title"] if v["data"]["title"] is not None else "",v["data"]["volume"] if v["data"]["volume"] is not None else "",v["data"]["chapter"],v["data"]["groupid"] if "groupid" in v["data"] else "",v["data"]["lang_short"],v["data"]["time"],))
						db.commit()
						cursor.close()
				db.close()
				self.logged(f"Download {id} success.")
				return manga

	def logged(self,*value):
		value = list(value)
		for i in range(len(value)):
			value[i] = str(value[i])
		text = "["+datetime.datetime.fromisoformat(datetime.datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')+"] "+''.join(value)
		print(text)
		logLocDir = scriptLocation+"/log"
		logLoc = logLocDir+"/"+datetime.datetime.fromisoformat(datetime.datetime.now().isoformat()).strftime('%Y-%m-%d')+".log"
		os.makedirs(logLocDir,exist_ok=True)
		with open(logLoc, "a") as file:
			file.write(text+"\n")

	def getCover(self,id):
		db = sqlite3.connect(config["db_location"])
		cursor = db.cursor()
		cursor.execute("SELECT image FROM series WHERE id = ?", (id,))
		data = cursor.fetchone()
		cursor.close()
		db.close()
		if data != None:
			return data[0]
		else:
			return 0

	def updateCover(self,id):
		data = self.getSerieInfo(id)
		data["extension"] = data["cover_extension"]
		data["artist"] = data["artist_string"]
		data["author"] = data["author_string"]
		db = sqlite3.connect(config["db_location"])

		cursor = db.cursor()
		cursor.execute("UPDATE series SET imageName = ?, image = ? WHERE id = ?", (data["cover_id"],data["cover"],data["id"],))
		db.commit()
		cursor.close()

		cursor = db.cursor()
		cursor.execute("SELECT value FROM settings WHERE key = 'saveCover'")
		save = cursor.fetchone()
		cursor.close()
		db.close()

		if save != None and save[0] == "yes":
			db = sqlite3.connect(config["db_location"])
			cursor = db.cursor()
			cursor.execute("SELECT value FROM settings WHERE key = 'coverDir'")
			foramt = cursor.fetchone()
			cursor.execute("SELECT value FROM settings WHERE key = 'saveDir'")
			lo = cursor.fetchone()
			cursor.close()
			db.close()
			if foramt != None and lo != None:
				lo = self.custom_format(lo[0]+foramt[0], **data)

				os.makedirs(os.path.dirname(lo),exist_ok=True)
				with open(lo, "wb") as file:
					file.write(data["cover"])
				self.logged(f"Cover saved as {lo}")
				return 1
			else:
				return 0
		else:
			return 0

	def getSerieInfo(self,id):
		out={}

		if id != "":
			r = requests.get(f"{apiUrl}/manga/{id}?includes[]=manga,cover_art,author,artist,tag,creator")
			self.logged(f"{apiUrl}/manga/{id}?includes[]=manga,cover_art,author,artist,tag,creator")
			manga = r.json()["data"]
			out["id"] = id
			out["lastUpdate"] = re.sub(r'([+-]\d{2}:\d{2})$','',manga["attributes"]["updatedAt"].replace("T"," "))
			out["author"] = []
			out["artist"] = []
			out["serie_original"] = manga["attributes"]["title"]["en"]
			out["serie"] = manga["attributes"]["title"]["en"]
			out["serie_force"] = None
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT forceName FROM series WHERE id = ?", (id,))
			fname = cursor.fetchone()
			cursor.close()
			if fname != None and fname[0] != None:
				out["serie"] = fname[0]
				out["serie_force"] = fname[0]

			for req in manga["relationships"]:
				if req["type"] == "author":
					out["author"].append(req["id"])
				elif req["type"] == "artist":
					out["artist"].append(req["id"])
				elif req["type"] == "cover_art":
					out["cover_id"] = req["id"]
			out["author_string"] = ",".join(out["author"])
			out["artist_string"] = ",".join(out["artist"])

			r = requests.get(f"{apiUrl}/cover/{out["cover_id"]}")
			self.logged(f"{apiUrl}/cover/{out["cover_id"]}")
			out["cover_full_name"] = r.json()["data"]["attributes"]["fileName"]
			out["cover_name"] = out["cover_full_name"].split(".")[0]
			out["cover_extension"] = "."+out["cover_full_name"].split(".")[1]

			r = requests.get(f"{imageUrl}/covers/{id}/{out["cover_full_name"]}")
			self.logged(f"{imageUrl}/covers/{id}/{out["cover_full_name"]}")
			out["cover"] = r.content

		else:
			out = 0

		return out

	def setForceName(self,value):
		value = json.loads(value)
		id = value["id"]
		name = value["name"] if value["name"] != "" else None
		db = sqlite3.connect(config["db_location"])
		cursor = db.cursor()
		cursor.execute("UPDATE series SET forceName = ? WHERE id = ?", (name,id,))
		db.commit()
		cursor.close()
		db.close()
		return 1

