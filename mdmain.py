import datetime
import os
import re
import sys
import time
import json
import sqlite3
import threading
import urllib.request
from functools import lru_cache
from mdbase import scriptLocation,config,url,headers,headersPost,progress,logged,settings,checkArg

class MDMain:
	def __init__(self):
		self.web = False

	def search(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"provider",
					"type":str,
					"req":True
				},
				{
					"var":"value",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		searchV = urllib.parse.quote(args["value"])
		re = []
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')

		if args["provider"] == "mangadex":
			r = self.request(f"{url["mangadex"]["api"]}/manga?includes[]=cover_art,author&order[relevance]=desc&originalLanguage[]=ja&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=erotica&contentRating[]=pornographic&title={searchV}")
			data = r["json"]["data"]
			for d in data:
				data = {"serieid": d["id"], "name": "", "authorid": "", "author": "", "artistid": "", "artist": "", "provider": "mangadex"}
				for t in d["attributes"]["title"]:
					data["name"] = d["attributes"]["title"][t]
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
				re.append(data)
    
		elif args["provider"] == "comick":
			r = self.request(f"{url["comick"]["api"]}/v1.0/search/?type=comic&page=1&limit=20&tachiyomi=true&showall=false&sort=rating&q={searchV}")
			data = json.loads(r["data"])
			for d in data:
				data = {"serieid": d["slug"], "name": "", "authorid": "", "author": "", "artistid": "", "artist": "", "provider": "comick"}
				data["name"] = d["title"]
				cr = self.request(f"{url["comick"]["api"]}/v1.0/comic/{d["slug"]}/?tachiyomi=true")
				cdata = json.loads(cr["data"])
				for a in cdata["authors"]:
					cursor = db.cursor()
					cursor.execute("SELECT COALESCE((SELECT name FROM author WHERE id = ?), 'Unknown')", (a["slug"],))
					name = cursor.fetchone()
					cursor.close()
					data["authorid"] = data["authorid"]+a["slug"]+", "
					data["author"] = data["author"]+name[0]+", "
				for a in cdata["artists"]:
					cursor = db.cursor()
					cursor.execute("SELECT COALESCE((SELECT name FROM author WHERE id = ?), 'Unknown')", (a["slug"],))
					name = cursor.fetchone()
					cursor.close()
					data["artistid"] = data["artistid"]+a["slug"]+", "
					data["artist"] = data["artist"]+name[0]+", "
				data["author"] = data["author"].rstrip(", ")
				data["authorid"] = data["authorid"].rstrip(", ")
				data["artist"] = data["artist"].rstrip(", ")
				data["artistid"] = data["artistid"].rstrip(", ")
				re.append(data)

		db.close()
		return re

	def searchChapter(self,searchV):
		r = self.request(f"{url["mangadex"]["api"]}/manga/{searchV}/feed")
		data = r["json"]["data"]
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
		cursor.execute("SELECT chapter.series, chapter.id, chapter.title, chapter.chapter, chapter.volume, chapter.got, chapter.tgroup, tgroup.name, chapter.time FROM chapter LEFT JOIN tgroup ON chapter.tgroup = tgroup.id WHERE series = ?", (serieid,))
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			serieid, chapterid, name, chapter, volume, dl, tgroupid, tgroup, time = d
			re.append({"serieid": serieid, "chapterid": chapterid, "name": name, "chapter": chapter, "volume": volume, "saved": "true" if dl==1 else "false" , "tgroupid": tgroupid, "tgroup": tgroup, "check": time})

		return re

	def knownSeries(self):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		sql = """
			SELECT s.id AS serieid, s.name AS name, s.h AS h, s.source AS source,
				GROUP_CONCAT(DISTINCT COALESCE(a1.name, 'Unknown')) AS authors,
				GROUP_CONCAT(DISTINCT COALESCE(a2.name, 'Unknown')) AS artists
			FROM series s
			LEFT JOIN author a1 ON ',' || s.author || ',' LIKE '%,' || a1.id || ',%'
			LEFT JOIN author a2 ON ',' || s.artist || ',' LIKE '%,' || a2.id || ',%'
		"""
		if "showH" in settings and settings["showH"] != "yes":
			sql = sql + " WHERE s.h IS NOT TRUE"
		sql = sql + " GROUP BY s.id, s.name ORDER BY s.id ASC"
		cursor.execute(sql)
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			serieid, name, h, source, author_names, artist_names = d
			re.append({"serieid": serieid, "name": name, "authors": author_names.replace(",",", "), "artists": artist_names.replace(",",", "), "h": h, "provider": source})

		return re

	def knownGroups(self):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("SELECT id,name,ignore,fake,deleted from tgroup")
		data = cursor.fetchall()
		cursor.close()
		db.close()
		re = []
		for d in data:
			tgroupid, name, ignore, fake, deleted = d
			re.append({"tgroupid": tgroupid, "name": name, "ignore": ignore if ignore == 1 else 0, "fake": fake if fake == 1 else 0, "deleted": deleted if deleted == 1 else 0})

		return re

	def knownGroupsset(self,value):
		groupid = value.split("mark")[0]
		mark = value.split("mark")[1][0:-1]
		markVal = value.split("mark")[1][-1]
		status=""
		if mark in ["ignore","fake","deleted"] and markVal in ["0","1"]:
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id FROM tgroup WHERE id = ?", (groupid,))
			group = cursor.fetchone()
			cursor.close()
			if group != None and groupid == group[0]:
				cursor = db.cursor()
				cursor.execute(f"UPDATE `tgroup` SET `{mark}` = ? WHERE id = ?", (markVal,groupid,))
				db.commit()
				cursor.close()
				status = "Saved"
			else:
				status = "No match group"
			db.close()

		return {"status":status}

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

		import mdbase
		mdbase.settings = mdbase.readSettings()
		global settings
		settings = mdbase.settings

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

	def addSerie(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"provider",
					"type":str,
					"req":True
				},
				{
					"var":"id",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		status=""
		self.logged(f"Adding: {args["id"]}")

		if args["id"] != "":
			if args["provider"] == "mangadex":
				dataSerie = self.getSerieInfo({"id":args["id"],"provider":"mangadex"})
				db = sqlite3.connect(config["db_location"])
				db.execute('PRAGMA journal_mode=WAL;')
				cursor = db.cursor()
				cursor.execute("SELECT id FROM series WHERE id = ?", (args["id"],))
				id = cursor.fetchone()
				cursor.close()
				if id != None and args["id"] == id[0]:
					status="Already added"
				else:
					cursor = db.cursor()
					cursor.execute("INSERT OR REPLACE INTO `series` (`id`,`name`,`forceName`,`lastUpdate`, `author`, `artist`, `imageName`, `image`, `lastCheck`, `favorite`, `fixedImage`, `priority`, `h`, `nameWarn`, `source`) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 'mangadex')", (args["id"], dataSerie["serie_original"], dataSerie["serie_original"], dataSerie["lastUpdate"],",".join(dataSerie["author"]) ,",".join(dataSerie["artist"]) ,dataSerie["cover_id"] ,dataSerie["cover"] , datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),)
					db.commit()
					cursor.close()
					status = f"Added: {dataSerie["serie_original"]}"

				db.close()
				thread=[]
				for a in dataSerie["author"] + dataSerie["artist"]:
					thread.append(threading.Thread(target=self.addAuthor,args=(a,args["provider"],)))
				for t in thread:
					t.start()
				for t in thread:
					t.join()
			elif args["provider"] == "comick":
				dataSerie = self.getSerieInfo({"id":args["id"],"provider":"comick"})
				db = sqlite3.connect(config["db_location"])
				db.execute('PRAGMA journal_mode=WAL;')
				cursor = db.cursor()
				cursor.execute("SELECT id FROM series WHERE id = ?", (args["id"],))
				id = cursor.fetchone()
				cursor.close()
				if id != None and args["id"] == id[0]:
					status="Already added"
				else:
					cursor = db.cursor()
					cursor.execute("INSERT OR REPLACE INTO `series` (`id`,`name`,`forceName`,`lastUpdate`, `author`, `artist`, `imageName`, `image`, `lastCheck`, `favorite`, `fixedImage`, `priority`, `h`, `nameWarn`, `source`) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 'comick')", (args["id"], dataSerie["serie_original"], dataSerie["serie_original"], dataSerie["lastUpdate"],",".join(dataSerie["author"]) ,",".join(dataSerie["artist"]) ,dataSerie["cover_id"] ,dataSerie["cover"] , datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),)
					db.commit()
					cursor.close()
					status = f"Added: {dataSerie["serie_original"]}"

				db.close()
				thread=[]
				for a in dataSerie["author"] + dataSerie["artist"]:
					thread.append(threading.Thread(target=self.addAuthor,args=(a,args["provider"],)))
				for t in thread:
					t.start()
				for t in thread:
					t.join()
		else:
			status = "No id query"

		self.logged(status)
		return {"status":status}

	def updateSerie(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"provider",
					"type":str,
					"req":True
				},
				{
					"var":"id",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]
		
		
		status=""
		self.logged(f"Updating: {args["id"]}")

		if args["id"] != "":
			if args["provider"] == "mangadex":
				db = sqlite3.connect(config["db_location"])
				db.execute('PRAGMA journal_mode=WAL;')
				cursor = db.cursor()
				cursor.execute("SELECT id FROM series WHERE id = ?", (args["id"],))
				name = cursor.fetchone()
				cursor.close()
				if name != None and args["id"] == name[0]:
					dataSerie = self.getSerieInfo({"id":args["id"],"provider":"mangadex"})

					cursor = db.cursor()
					cursor.execute("UPDATE `series` SET `name` = ?, `lastUpdate` = ?, `author` = ?, `author` = ?, `imageName` = ?, `image` = ?, `lastCheck` = ? WHERE id = ?", (dataSerie["serie_original"], dataSerie["lastUpdate"], ",".join(dataSerie["author"]), ",".join(dataSerie["artist"]), dataSerie["cover_id"], dataSerie["cover"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),args["id"],))
					db.commit()
					cursor.close()
					status = f"Updated: {dataSerie["serie_original"]}"

					db.close()
					thread=[]
					for a in dataSerie["author"] + dataSerie["artist"]:
						thread.append(threading.Thread(target=self.addAuthor,args=(a,args["provider"],)))
					for t in thread:
						t.start()
					for t in thread:
						t.join()
			elif args["provider"] == "comick":
				db = sqlite3.connect(config["db_location"])
				db.execute('PRAGMA journal_mode=WAL;')
				cursor = db.cursor()
				cursor.execute("SELECT id FROM series WHERE id = ?", (args["id"],))
				name = cursor.fetchone()
				cursor.close()
				if name != None and args["id"] == name[0]:
					dataSerie = self.getSerieInfo({"id":args["id"],"provider":"comick"})

					cursor = db.cursor()
					cursor.execute("UPDATE `series` SET `name` = ?, `lastUpdate` = ?, `author` = ?, `author` = ?, `imageName` = ?, `image` = ?, `lastCheck` = ? WHERE id = ?", (dataSerie["serie_original"], dataSerie["lastUpdate"], ",".join(dataSerie["author"]), ",".join(dataSerie["artist"]), dataSerie["cover_id"], dataSerie["cover"], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),args["id"],))
					db.commit()
					cursor.close()
					status = f"Updated: {dataSerie["serie_original"]}"

					db.close()
					thread=[]
					for a in dataSerie["author"] + dataSerie["artist"]:
						thread.append(threading.Thread(target=self.addAuthor,args=(a,args["provider"],)))
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

	def addAuthor(self,id,provider):
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
				if provider == "mangadex":
					r = self.request(f"{url["mangadex"]["api"]}/author/{id}")
					author = r["json"]["data"]

					cursor = db.cursor()
					cursor.execute("INSERT OR REPLACE INTO `author` (`id`,`name`,`favorite`) VALUES (?, ?, 0)", (id,author["attributes"]["name"],))
					db.commit()
					cursor.close()
					status = f"Added: {author["attributes"]["name"]}"
				elif provider == "comick":
					r = self.request(f"{url["comick"]["api"]}/people/{id}")
					author = json.loads(r["data"])

					cursor = db.cursor()
					cursor.execute("INSERT OR REPLACE INTO `author` (`id`,`name`,`favorite`) VALUES (?, ?, 0)", (id,author["people"]["name"],))
					db.commit()
					cursor.close()
					status = f"Added: {author["people"]["name"]}"
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

	def getChapterInfoToLestest(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"provider",
					"type":str,
					"req":True
				},
				{
					"var":"id",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		id = args["id"]
		provider = args["provider"]
		natsort = lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s or '')]
		
		if id != "" and provider != "":
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id,name,h FROM series WHERE id = ?", (id,))
			serie = cursor.fetchone()
			cursor.execute("SELECT id,name FROM tgroup WHERE ignore = true")
			igGroup = {i[0]: i[1] for i in cursor.fetchall()}
			lang = settings["languages"].split(",")
			location = settings["saveDir"]
			format = settings["saveName"]
			if serie != None and serie[2] == "1":
				location = settings["saveHDir"]
				format = settings["hSaveName"]
			cursor.close()
			if serie != None and id == serie[0]:
				if provider == "mangadex":
					dataSerie = self.getSerieInfo({"id":id,"provider":provider})
					progress.update(id, {"status": "getting chapter info", "progress": "0", "subprogress": "0"})
					manga = []
					mangaVol = {}
					allChapter = []
					alchp = False
					alchplimit = 100
					alchpoffset = 0
					langStr = ""
					for l in lang:
						if langStr == "":
							langStr = f"translatedLanguage[]={l}"
						else:
							langStr = f"{langStr}&translatedLanguage[]={l}"

					while alchp == False:
						r = self.request(f"{url["mangadex"]["api"]}/manga/{id}/feed?limit={alchplimit}&offset={alchpoffset}&{langStr}&includes[]=scanlation_group&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=safe&contentRating[]=erotica&contentRating[]=pornographic")
						chp = r["json"]
						allChapter.extend(chp["data"])
						if len(allChapter) == chp["total"]:
							alchp = True
						else:
							alchpoffset=alchplimit+alchpoffset
						time.sleep(1)

					for i,chp in enumerate(allChapter, start=1):
						progress.update(id, {"status": f"getting chapter info {i}/{len(allChapter)}", "progress": str(round((i/len(allChapter))*100,2)), "subprogress": "0"})
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
										cursor.execute("INSERT INTO `tgroup` (`id`,`name`,`ignore`,`fake`,`deleted`) VALUES (?, ?, ?, ?, 0)", (chpRel["id"],chpRel["attributes"]["name"],chpRel["attributes"]["official"],chpRel["attributes"]["official"],))
										db.commit()
										data["group"] = chpRel["attributes"]["name"]
										data["groupid"] = chpRel["id"]
									cursor.close()
							r = location + format
							if "groupid" in data and data["groupid"] in igGroup:
								self.logged(f"Ignore chapter {data["chapter"]} from {data["group"]}")
								continue
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
								p["data"]["downloaded"] = True
							elif chp != None and p["data"]["id"] == chp[0] and chp[1] == False:
								p["data"]["downloaded"] = False
							else:
								p["data"]["downloaded"] = False
								cursor = db.cursor()
								cursor.execute("INSERT INTO `chapter` (`id`,`series`,`title`,`volume`,`chapter`,`tgroup`,`language`,`time`,`got`) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)", (p["data"]["id"],serie[0],p["data"]["title"] if p["data"]["title"] is not None else "",p["data"]["volume"] if p["data"]["volume"] is not None else "",p["data"]["chapter"],p["data"]["groupid"] if "groupid" in p["data"] else "",p["data"]["lang_short"],datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
								cursor.close()
							manga.append(p)
					db.commit()
					db.close()
					progress.update(id, {"status": "got all chapter info", "progress": "100", "subprogress": "0"})
					return manga
				elif provider =="comick":
					dataSerie = self.getSerieInfo({"id":id,"provider":provider})
					progress.update(id, {"status": "getting chapter info", "progress": "0", "subprogress": "0"})
					manga = []
					mangaVol = {}
					allChapter = []
					alchp = False
					alchplimit = 100
					alchppage = 1
					langStr = ",".join(lang)

					while alchp == False:
						r = self.request(f"{url["comick"]["api"]}/comic/{dataSerie["hid"]}/chapters?limit={alchplimit}&page={alchppage}&lang={langStr}&chap-order=1")
						chp = json.loads(r["data"])
						allChapter.extend(chp["chapters"])
						if len(allChapter) == chp["total"]:
							alchp = True
						else:
							alchppage=alchppage+1
						time.sleep(1)

					for i,chp in enumerate(allChapter, start=1):
						progress.update(id, {"status": f"getting chapter info {i}/{len(allChapter)}", "progress": str(round((i/len(allChapter))*100,2)), "subprogress": "0"})
						if chp["lang"] in lang:
							data = {}
							data["id"] = chp["hid"]
							data["serie"] = dataSerie["serie"]
							data["volume"] = chp["vol"]
							data["chapter"] = chp["chap"]
							data["title"] = chp["title"]
							data["lang_short"] = chp["lang"]
							for chpRel in chp["md_chapters_groups"]:
								cursor = db.cursor()
								cursor.execute("SELECT id FROM tgroup WHERE id = ?", (chpRel["md_groups"]["slug"],))
								tg = cursor.fetchone()
								if tg != None and chpRel["md_groups"]["slug"] == tg[0]:
									data["group"] = chpRel["md_groups"]["title"]
									data["groupid"] = chpRel["md_groups"]["slug"]
								else:
									cursor.execute("INSERT INTO `tgroup` (`id`,`name`,`ignore`,`fake`,`deleted`) VALUES (?, ?, 0, 0, 0)", (chpRel["md_groups"]["slug"],chpRel["md_groups"]["title"],))
									db.commit()
									data["group"] = chpRel["md_groups"]["title"]
									data["groupid"] = chpRel["md_groups"]["slug"]
									cursor.close()
							r = location + format
							if "groupid" in data and data["groupid"] in igGroup:
								self.logged(f"Ignore chapter {data["chapter"]} from {data["group"]}")
								continue
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
								p["data"]["downloaded"] = True
							elif chp != None and p["data"]["id"] == chp[0] and chp[1] == False:
								p["data"]["downloaded"] = False
							else:
								p["data"]["downloaded"] = False
								cursor = db.cursor()
								cursor.execute("INSERT INTO `chapter` (`id`,`series`,`title`,`volume`,`chapter`,`tgroup`,`language`,`time`,`got`) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)", (p["data"]["id"],serie[0],p["data"]["title"] if p["data"]["title"] is not None else "",p["data"]["volume"] if p["data"]["volume"] is not None else "",p["data"]["chapter"],p["data"]["groupid"] if "groupid" in p["data"] else "",p["data"]["lang_short"],datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
								cursor.close()
							manga.append(p)
					db.commit()
					db.close()
					progress.update(id, {"status": "got all chapter info", "progress": "100", "subprogress": "0"})
					return manga
		db.close()
		return {}

	def downloadToLestest(self,id):
		if id != "":
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id,title,chapter,volume,tgroup,language,time,got FROM chapter WHERE series = ?", (id,))
			manga = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
			cursor.execute("SELECT source,h FROM series WHERE id = ?", (id,))
			serie = {}
			location = settings["saveDir"]
			format = settings["saveName"]
			seriedb = cursor.fetchone()
			if seriedb != None and seriedb[0] != "":
				serie = self.getSerieInfo({"id":id,"provider":seriedb[0]})
			else:
				serie = self.getSerieInfo({"id":id,"provider":"mangadex"})
			if seriedb != None and seriedb[1] == "1":
				location = settings["saveHDir"]
				format = settings["hSaveName"]
			cursor.close()
			progress.update(id, {"status": "downloading", "progress": "0", "subprogress": "0"})
			for i,m in enumerate(manga, start=1):
				progress.update(id, {"status": f"downloading {i}/{len(manga)}", "progress": str(round((i/len(manga))*100,2)), "subprogress": "0"})
				if m["got"] == False:
					if serie["provider"] == "mangadex":
						r = self.request(f"{url["mangadex"]["api"]}/at-home/server/{m["id"]}")
						chp = r["json"]
						m["serie"] = serie["serie"]
						cursor = db.cursor()
						cursor.execute("SELECT name FROM tgroup WHERE id = ?", (m["tgroup"],))
						g = cursor.fetchone()
						m["group"] = g[0] if g != None else ""
						m["authors_artists"] = ",".join(serie["author"] + serie["artist"])
						m["volume"] = m["volume"] if m["volume"] is not None else "0"
						m["chapter"] = m["chapter"] if m["chapter"] is not None else "0"
						m["title"] = m["title"] if m["title"] is not None else ""
						m["lang_short"] = m["language"]

						for j,p in enumerate(chp["chapter"]["data"], start=1): 
							progress.update(id, {"status": f"downloading {i}/{len(manga)} page {j}/{len(chp["chapter"]["data"])}", "progress": str(round((i/len(manga))*100,2)), "subprogress": str(round((j/len(chp["chapter"]["data"]))*100,2))})
							m["page"] = str(j)
							m["extension"] = os.path.splitext(p)[1]
							m["time"] = datetime.datetime.fromisoformat(datetime.datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
							r = self.downloadPage(f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}", self.custom_format(location+format, **m))
							report = {
								"url": f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}",
								"success": True if r["status"] == 200 else False,
								"bytes": r["size"],
								"duration": round(r["usedtime"] * 1000),
								"cached": True if r["status"] == 200 else False
							}
							urllib.request.Request("https://api.mangadex.network/report", data=urllib.parse.urlencode(report).encode(), headers=headersPost)
							if r["status"] != 200:
								self.logged(f"Download {serie["serie"]} - chapter {m['chapter']} failed. (page:{j} url:{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p})")
								break
						else:
							cursor = db.cursor()
							cursor.execute("UPDATE `chapter` SET `got` = 1 WHERE `id` = ?", (m["id"],))				
							db.commit()
							cursor.close()
							self.logged(f"Download {serie["serie"]} - chapter {m['chapter']} success.")

					elif serie["provider"] == "comick":
						r = self.request(f"{url["comick"]["api"]}/chapter/{m["id"]}/get_images")
						chp = json.loads(r["data"])
						m["serie"] = serie["serie"]
						cursor = db.cursor()
						cursor.execute("SELECT name FROM tgroup WHERE id = ?", (m["tgroup"],))
						g = cursor.fetchone()
						m["group"] = g[0] if g != None else ""
						m["authors_artists"] = ",".join(serie["author"] + serie["artist"])
						m["volume"] = m["volume"] if m["volume"] is not None else "0"
						m["chapter"] = m["chapter"] if m["chapter"] is not None else "0"
						m["title"] = m["title"] if m["title"] is not None else ""
						m["lang_short"] = m["language"]
						m = {**serie, **m}

						for j,p in enumerate(chp, start=1): 
							progress.update(id, {"status": f"downloading {i}/{len(manga)} page {j}/{len(chp)}", "progress": str(round((i/len(manga))*100,2)), "subprogress": str(round((j/len(chp))*100,2))})
							m["page"] = str(j)
							m["extension"] = os.path.splitext(p["b2key"])[1]
							m["time"] = datetime.datetime.fromisoformat(datetime.datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
							r = self.downloadPage(f"{url["comick"]["image"]}/{p["b2key"]}", self.custom_format(location+format, **m))
							if r["status"] != 200:
								self.logged(f"Download {serie["serie"]} - chapter {m['chapter']} failed. (page:{j} url:{url["comick"]["image"]}/{p["b2key"]})")
								break
						else:
							cursor = db.cursor()
							cursor.execute("UPDATE `chapter` SET `got` = 1 WHERE `id` = ?", (m["id"],))				
							db.commit()
							cursor.close()
							self.logged(f"Download {serie["serie"]} - chapter {m['chapter']} success.")

				progress.update(id, {"status": f"download {i}/{len(manga)}", "progress": str(round((i/len(manga))*100,2)), "subprogress": "0"})
			db.close()
			self.logged(f"Download {serie["serie"]} success.")
			progress.update(id, {"status": "download all", "progress": "100", "subprogress": "0"})
			return manga

	def downloadPage(self,url,location):
		if location != "" and url != "":
			out = {}
			os.makedirs(os.path.dirname(location),exist_ok=True)
			req = urllib.request.Request(url, headers=headers)
			try:
				with urllib.request.urlopen(req) as r:
					out["status"] = r.getcode()
					out["size"] = int(r.headers.get("Content-Length", 0))
					out["download"] = 0
					out["block"] = 4096
					out["start"] = time.time()
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
								out["download"] += len(data)
								out["usedtime"] = time.time() - out["start"]
								out["speed"] = out["download"] / out["usedtime"] if out["usedtime"] > 0 else 0

								if out["speed"] > 4_000_000:
									out["block"] = 65536
								elif out["speed"] > 1_000_000:
									out["block"] = 16384
								else:
									out["block"] = 4096
								
								out["percent"] = out["download"] / out["size"] * 100 if out["size"] else 0
								sys.stdout.write(f"\rDownloading: {out["percent"]:.2f}% ({out["download"]}/{out["size"]} bytes) | Speed: {out["speed"]/1_000:.2f} KB/s")
								sys.stdout.flush()
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
				self.logged(f"Error downloading {url}: {str(e)}")
				out["status"] = 500
		else:
			out["status"] = 404
			self.logged(f"downloadPage no url or location")
		return out

	def markSerieH(self,value):
		serieid = value.split("mark")[0]
		markVal = value.split("mark")[1][-1]
		status=""
		if markVal in ["0","1"]:
			db = sqlite3.connect(config["db_location"])
			db.execute('PRAGMA journal_mode=WAL;')
			cursor = db.cursor()
			cursor.execute("SELECT id FROM series WHERE id = ?", (serieid,))
			serie = cursor.fetchone()
			cursor.close()
			if serie != None and serieid == serie[0]:
				cursor = db.cursor()
				cursor.execute("UPDATE `series` SET `h` = ? WHERE id = ?", (markVal, serieid,))
				db.commit()
				cursor.close()
				status = "Saved"
			else:
				status = "No match serie"
			db.close()
		else:
			status="not valid boolean"

		return {"status":status}

	@staticmethod
	@lru_cache(maxsize=500)
	def request(url,type="get"):
		if type == "get":
			logged(f"request: {url}")
			logged(f"user-agent: {headers["User-Agent"]}")
			r = {}
			req = urllib.request.Request(url, headers=headers)
			try:
				with urllib.request.urlopen(req) as response:
					r["status"] = response.getcode()
					r["data"] = response.read()
					try:
						r["text"] = r["data"].decode("utf-8")
					except:
						r["text"] = ""
					try:
						r["json"] = json.loads(r["text"])
					except:
						r["json"] = {}
				logged(f"request: {url} complete")
			except urllib.error.HTTPError as e:
				r["status"] = e.code
				r["text"] = ""
				r["json"] = {}
				logged(f"request: {url} error")
		else:
			return 0
		return r

	def logged(self,*value):
		logged(value)
		value = list(value)
		for i in range(len(value)):
			value[i] = str(value[i])
		time = datetime.datetime.fromisoformat(datetime.datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
		if self.web:
			try:
				from mdweb import send_message
				send_message(''.join(value), timestamp=time)
			except (ImportError, AttributeError):
				pass

	def getAppBG(self):
		try:
			color = tuple(int(settings["appBGColor"].lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
		except:
			color = (0,0,0)
		db = sqlite3.connect(config["db_location"])
		cursor = db.cursor()
		cursor.execute("SELECT id FROM series WHERE id = ?", (settings["appBGCover"],))
		serie = cursor.fetchone()
		cursor.close()
		db.close()
		if settings["appBGType"] == "cover" and serie != None and settings["appBGCover"] == serie[0]:
			return self.getSerieInfo({"id":settings["appBGCover"],"provider":"mangadex"})["cover"]
		else:
			import zlib, struct
			ihdr = b'IHDR' + struct.pack('!IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
			ihdr = struct.pack('!I', len(ihdr) - 4) + ihdr + struct.pack('!I', zlib.crc32(ihdr) & 0xffffffff)
			raw = b'\x00' + bytes(color)
			comp = zlib.compress(raw)
			idat = b'IDAT' + comp
			idat = struct.pack('!I', len(comp)) + idat + struct.pack('!I', zlib.crc32(idat) & 0xffffffff)
			iend = struct.pack('!I', 0) + b'IEND' + struct.pack('!I', zlib.crc32(b'IEND') & 0xffffffff)
			return b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend

	def getCover(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"provider",
					"type":str,
					"req":True
				},
				{
					"var":"id",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		db = sqlite3.connect(config["db_location"])
		cursor = db.cursor()
		cursor.execute("SELECT image FROM series WHERE id = ?", (args["id"],))
		data = cursor.fetchone()
		cursor.close()
		db.close()
		if data != None:
			return data[0]
		else:
			if args["provider"]=="mangadex":
				return self.getSerieInfo({"id":args["id"],"provider":"mangadex"})["cover"]
			elif args["provider"]=="comick":
				return self.getSerieInfo({"id":args["id"],"provider":"comick"})["cover"]

	def updateCover(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"provider",
					"type":str,
					"req":True
				},
				{
					"var":"id",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		db = sqlite3.connect(config["db_location"])
		cursor = db.cursor()
		cursor.execute("SELECT id FROM series WHERE id = ?", (args["id"],))
		id = cursor.fetchone()
		cursor.close()
		if id != None and args["id"] == id[0]:
			progress.update(args["id"], {"status": "downloading cover", "progress": 0})
			data = self.getSerieInfo({"id":args["id"],"provider":args["provider"]})
			data["extension"] = data["cover_extension"]
			data["artist"] = data["artist_string"]
			data["author"] = data["author_string"]

			cursor = db.cursor()
			cursor.execute("UPDATE series SET imageName = ?, image = ? WHERE id = ?", (data["cover_id"],data["cover"],data["id"],))
			db.commit()
			cursor.close()
			progress.update(args["id"], {"status": "saved cover to db", "progress": 100})

			if settings["saveCover"] == "yes":
				progress.update(args["id"], {"status": "saving cover to file", "progress": 0})
				format = settings["coverDir"]
				lo = settings["saveDir"]

				cursor = db.cursor()
				cursor.execute("SELECT h FROM series WHERE id = ?", (args["id"],))
				h = cursor.fetchone()
				cursor.close()
				db.close()
				if h != None and h[0] == "1":
					format = settings["coverHDir"]
					lo = settings["saveHDir"]
				print(lo)
				lo = self.custom_format(lo+format, **data)
				
				os.makedirs(os.path.dirname(lo),exist_ok=True)
				with open(lo, "wb") as file:
					file.write(data["cover"])
				self.logged(f"Cover saved as {lo}")
				progress.update(args["id"], {"status": "saved cover to file", "progress": 100})
				
				db.close()
				return 1
			else:
				db.close()
				return 0
		else:
			db.close()
			return 0

	def getSerieInfo(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"provider",
					"type":str,
					"req":True
				},
				{
					"var":"id",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		out={}

		if args["id"] != "":
			if args["provider"] == "mangadex":
				r = self.request(f"{url["mangadex"]["api"]}/manga/{args["id"]}?includes[]=manga,cover_art,author,artist,tag,creator")
				manga = r["json"]["data"]
				out["provider"] = args["provider"]
				out["id"] = args["id"]
				out["lastUpdate"] = re.sub(r'([+-]\d{2}:\d{2})$','',manga["attributes"]["updatedAt"].replace("T"," "))
				out["author"] = []
				out["artist"] = []
				out["serie_original"] = manga["attributes"]["title"]["en"]
				out["serie"] = manga["attributes"]["title"]["en"]
				out["serie_force"] = None
				db = sqlite3.connect(config["db_location"])
				db.execute('PRAGMA journal_mode=WAL;')
				cursor = db.cursor()
				cursor.execute("SELECT forceName,name FROM series WHERE id = ?", (args["id"],))
				fname = cursor.fetchone()
				cursor.close()
				if fname != None and fname[1] != out["serie_original"]:
					cursor = db.cursor()
					cursor.execute("UPDATE series SET name = ? WHERE id = ?", (out["serie_original"],args["id"],))
					db.commit()
					logged(f"Change serie name from \"{fname[1]}\" to \"{out["serie_original"]}\"")
				if fname != None and fname[0] != None:
					out["serie"] = fname[0]
					out["serie_force"] = fname[0]
				db.close()

				for req in manga["relationships"]:
					if req["type"] == "author":
						out["author"].append(req["id"])
					elif req["type"] == "artist":
						out["artist"].append(req["id"])
					elif req["type"] == "cover_art":
						out["cover_id"] = req["id"]
				out["author_string"] = ",".join(out["author"])
				out["artist_string"] = ",".join(out["artist"])
				for req in manga["relationships"]:
					if req["type"] == "author":
						out["author"].append(req["id"])
					elif req["type"] == "artist":
						out["artist"].append(req["id"])
					elif req["type"] == "cover_art":
						out["cover_id"] = req["id"]
				out["author_string"] = ",".join(out["author"])
				out["artist_string"] = ",".join(out["artist"])

				r = self.request(f"{url["mangadex"]["api"]}/cover/{out["cover_id"]}")
				out["cover_full_name"] = r["json"]["data"]["attributes"]["fileName"]
				out["cover_name"] = out["cover_full_name"].split(".")[0]
				out["cover_extension"] = "."+out["cover_full_name"].split(".")[1]
				r = self.request(f"{url["mangadex"]["api"]}/cover/{out["cover_id"]}")
				out["cover_full_name"] = r["json"]["data"]["attributes"]["fileName"]
				out["cover_name"] = out["cover_full_name"].split(".")[0]
				out["cover_extension"] = "."+out["cover_full_name"].split(".")[1]

				r = self.request(f"{url["mangadex"]["image"]}/covers/{args["id"]}/{out["cover_full_name"]}")
				out["cover"] = r["data"]
    
			elif args["provider"] == "comick":
				r = self.request(f"{url["comick"]["api"]}/comic/{args["id"]}/?tachiyomi=true")
				manga = json.loads(r["data"])
				out["provider"] = args["provider"]
				out["id"] = args["id"]
				out["hid"] = manga["comic"]["hid"]
				out["lastUpdate"] = None
				out["author"] = []
				out["artist"] = []
				out["serie_original"] = manga["comic"]["title"]
				out["serie"] = manga["comic"]["title"]
				out["serie_force"] = None
				db = sqlite3.connect(config["db_location"])
				db.execute('PRAGMA journal_mode=WAL;')
				cursor = db.cursor()
				cursor.execute("SELECT forceName,name FROM series WHERE id = ?", (args["id"],))
				fname = cursor.fetchone()
				cursor.close()
				if fname != None and fname[1] != out["serie_original"]:
					cursor = db.cursor()
					cursor.execute("UPDATE series SET name = ? WHERE id = ?", (out["serie_original"],args["id"],))
					db.commit()
					logged(f"Change serie name from \"{fname[1]}\" to \"{out["serie_original"]}\"")
				if fname != None and fname[0] != None:
					out["serie"] = fname[0]
					out["serie_force"] = fname[0]
				db.close()
    
				for a in manga["authors"]:
					out["author"].append(a["slug"])
				for a in manga["artists"]:
					out["artist"].append(a["slug"])
				out["author_string"] = ",".join(out["author"])
				out["artist_string"] = ",".join(out["artist"])

				out["cover_id"] = manga["comic"]["md_covers"][0]["b2key"]
				out["cover_full_name"] = out["cover_id"]
				out["cover_name"] = out["cover_full_name"].split(".")[0]
				out["cover_extension"] = "."+out["cover_full_name"].split(".")[1]
				print(out["cover_extension"])
				
				r = self.request(f"{url["comick"]["image"]}/{out["cover_id"]}")
				out["cover"] = r["data"]
		else:
			out = 0

		return out

	def setForceName(self,value):
		value = json.loads(value)
		id = value["id"]
		name = value["name"] if value["name"] != "" else None
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("UPDATE series SET forceName = ? WHERE id = ?", (name,id,))
		db.commit()
		cursor.close()
		db.close()
		return 1

	def getQueue():
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("SELECT id,type from fetch")
		queue = cursor.fetchall()

