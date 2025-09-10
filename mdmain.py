import os
import re
import sys
import time
import json
import sqlite3
import threading
import urllib.request
from datetime import datetime
from functools import lru_cache
from mdbase import config,url,headers,headersPost,progress,logged,settings,checkArg,provider,queryDB,insereplaceDB,updateDB

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
			r = self.request(f"{url["mangadex"]["api"]}/manga?includes[]=cover_art,author&order[relevance]=desc&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=erotica&contentRating[]=pornographic&title={searchV}")
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
			
			for a in d["relationships"]:
				if a["type"] == "scanlation_group":
					db = sqlite3.connect(config["db_location"])
					cursor = db.cursor()
					cursor.execute("SELECT COALESCE((SELECT name FROM tgroup WHERE id = ?), 'Unknown')", (a["id"],))
					name = cursor.fetchone()
					cursor.close()
					db.close()
					data["tgroupid"] = data["tgroupid"]+a["id"]+", "
					data["tgroup"] = data["tgroup"]+name[0]+", "
			data["tgroup"] = data["tgroup"].rstrip(", ")
			data["tgroupid"] = data["tgroupid"].rstrip(", ")
			data["tgroup"] = data["tgroup"].rstrip(", ")
			data["tgroupid"] = data["tgroupid"].rstrip(", ")

			re.append(data)
		re=sorted(re, key=lambda x: (float((x["volume"]) if x["volume"] is not None else -1), float(x["chapter"]) if x["chapter"] is not None else 0))

		return re

	def knownSeriesChapter(self,serieid):
		re = []
		for d in queryDB(select=["chapter.series AS serieid", "chapter.id AS chapterid", "chapter.title AS name", "chapter.chapter AS chapter", "chapter.volume AS volume", "chapter.got AS dl", "chapter.tgroup AS tgroupid", "tgroup.name AS tgroup", "chapter.time AS time"], table=["chapter LEFT JOIN tgroup ON chapter.tgroup = tgroup.id"], where={"series": serieid}):
			re.append({"serieid": d["serieid"], "chapterid": d["chapterid"], "name": d["name"], "chapter": d["chapter"], "volume": d["volume"], "saved": "true" if d["dl"]==1 else "false" , "tgroupid": d["tgroupid"], "tgroup": d["tgroup"], "check": d["time"]})

		return re

	def knownSeries(self):
		db = sqlite3.connect(config["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		sql = """
			SELECT s.id AS serieid, COALESCE(s.forceName, s.name) AS name, s.h AS h, s.source AS source,
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
		re = []
		for data in queryDB(select=["id","name","ignore","fake","deleted"],table=["tgroup"]):
			re.append({"tgroupid": data["id"], "name": data["name"], "ignore": data["ignore"] if data["ignore"] == 1 else 0, "fake": data["fake"] if data["fake"] == 1 else 0, "deleted": data["deleted"] if data["deleted"] == 1 else 0})

		return re

	def knownGroupsset(self,value):
		groupid = value.split("mark")[0]
		mark = value.split("mark")[1][0:-1]
		markVal = value.split("mark")[1][-1]
		status=""
		if mark in ["ignore","fake","deleted"] and markVal in ["0","1"]:
			group = queryDB(select=["id"],table=["tgroup"],where={"id":groupid})
			if len(group) > 0 and groupid == group[0]["id"]:
				updateDB(values={mark: markVal}, table=["tgroup"], where={"id": groupid})
				status = "Saved"
			else:
				status = "No match group"

		return {"status":status}

	def knownSeriesData(self,id,col):
		re = []
		for data in queryDB(select=["id","name"],table=["series"]):
			re.append({"serieid": data["id"], "name": data["name"]})

		return re

	def setSettings(self,value):
		settingsList = json.loads(value)
		for setting in settingsList:
			updateDB(table=["settings"], values={"value":setting["value"]}, where={"key":setting["id"]})

		import mdbase
		mdbase.settings = mdbase.readSettings()
		global settings
		settings = mdbase.settings

		return {"status":"Saved settings"}

	def getSettings(self):
		data = queryDB(select=["key","name","value"],table=["settings"],where={"user":"1"})
		re = []
		for d in data:
			re.append({"id": d["key"], "name": d["name"], "value": d["value"]})

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

		if args["provider"] in provider:
			dataSerie = self.getSerieInfo({"id":args["id"],"provider":args["provider"]})
			manga = queryDB(select=["id"],table=["series"],where={"id":args["id"]})
			if len(manga) > 0 and args["id"] == manga[0]["id"]:
				status="Already added"
			else:
				insereplaceDB(table=["series"],values={"id":args["id"], "name":dataSerie["serie_original"], "forceName":dataSerie["serie_original"], "lastUpdate":dataSerie["lastUpdate"], "author":",".join(dataSerie["author"]), "artist":",".join(dataSerie["artist"]), "imageName":dataSerie["cover_id"], "image":dataSerie["cover"], "lastCheck":datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "favorite":"0", "fixedImage":"0", "priority":"0", "h":"0", "nameWarn":"0", "source":args["provider"]})
				status = f"Added: {dataSerie["serie_original"]}"

			thread=[]
			for a in dataSerie["author"] + dataSerie["artist"]:
				thread.append(threading.Thread(target=self.addAuthor,args=({"id":a,"provider":args["provider"]},)))
			for t in thread:
				t.start()
			for t in thread:
				t.join()
		else:
			status = "Not valid id/provider"

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

		if args["provider"] in provider:
			manga = queryDB(select=["id"],table=["series"],where={"id":args["id"]})
			if len(manga) > 0 and args["id"] == manga[0]["id"]:
				dataSerie = self.getSerieInfo({"id":args["id"],"provider":args["provider"]})

				updateDB(values={"name":dataSerie["serie_original"], "lastUpdate":dataSerie["lastUpdate"], "author":",".join(dataSerie["author"]), "artist":",".join(dataSerie["artist"]), "imageName":dataSerie["cover_id"], "image":dataSerie["cover"], "lastCheck":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, table=["series"], where={"id":args["id"]})
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

	def addAuthor(self,args):
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
		self.logged(f"Adding: {id}")

		
		authordb = queryDB(select=["id"],table=["author"],where={"id":args["id"]})
		if len(authordb) > 0 and args["id"] == authordb[0]["id"]:
			status="Already added"
		else:
			if args["provider"] in provider:
				r = []
				if args["provider"] == "mangadex":
					r = self.request(f"{url["mangadex"]["api"]}/author/{args["id"]}")
				elif args["provider"] == "comick":
					r = self.request(f"{url["comick"]["api"]}/people/{args["id"]}")
				author = r["json"]["data"]

				if args["provider"] == "mangadex":
					insereplaceDB(table=["author"],values={"id":args["id"], "name":author["attributes"]["name"], "favorite":"0"})
				elif args["provider"] == "comick":
					insereplaceDB(table=["author"],values={"id":args["id"], "name":author["people"]["name"], "favorite":"0"})
				status = f"Added: {author["attributes"]["name"]}"

		self.logged(status)
		return {"status":status}

	def formatToReal(self,data,format):
		# for ref only
		data["serie"] = data.get('serie',"") #w
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
		data["time"] = data.get('time',"") #w
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
		natsort = lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s or '')]
		
		serieDB = queryDB(select=["id","name","h"],table=["series"],where={"id":id})
		if args["provider"] in provider and len(serieDB) > 0 and id == serieDB[0]["id"]:
			igGroup = {g["id"] for g in queryDB(select=["id"],table=["tgroup"],where={"ignore":"1"})}
			fkGroup = {g["id"] for g in queryDB(select=["id"],table=["tgroup"],where={"fake":"1"})}
			lang = settings["languages"].split(",")
			location = settings["saveHDir"] if serieDB[0]["h"] else settings["saveDir"]
			format = settings["hSaveName"] if serieDB[0]["h"] else settings["saveName"]
			dataSerie = self.getSerieInfo({"id":id,"provider":args["provider"]})
			progress.update(id, {"status": "getting chapter info", "progress": "0", "subprogress": "0"})
			manga = []
			mangaVol = {}
			allChapter = []
			alchp = False
			alchplimit = 100
			alchpoffset = 0
			alchppage = 1

			if args["provider"] == "mangadex":
				langStr = ("translatedLanguage[]=" if len(lang)>0 else "") + "&translatedLanguage[]=".join(lang)
				while alchp == False:
					r = self.request(f"{url["mangadex"]["api"]}/manga/{id}/feed?limit={alchplimit}&offset={alchpoffset}&{langStr}&includes[]=scanlation_group&contentRating[]=safe&contentRating[]=suggestive&contentRating[]=safe&contentRating[]=erotica&contentRating[]=pornographic")
					chp = r["json"]
					allChapter.extend([{
							"id":c['id'], 
							"volume":c["attributes"]["volume"], 
							"chapter":c["attributes"]["chapter"], 
							"title":c["attributes"]["title"], 
							"lang_short":c["attributes"]["translatedLanguage"],
							"group":",".join([g["attributes"]["name"] for g in c["relationships"] if g["type"] == "scanlation_group"]),
							"groupid":",".join([g["id"] for g in c["relationships"] if g["type"] == "scanlation_group"]),
							"group_combid":[{"id":g["id"],"name":g["attributes"]["name"],"fake":"1" if g["attributes"]["official"] else "0"} for g in c["relationships"] if g["type"] == "scanlation_group"]
						} for c in chp["data"]])
					if len(allChapter) == chp["total"]:
						alchp = True
					else:
						alchpoffset=alchplimit+alchpoffset
					progress.update(id, {"status": "getting chapter info", "progress": str(round((len(allChapter)/chp["total"])*100,2)), "subprogress": "0"})
					time.sleep(1)
			elif args["provider"] == "comick":
				langStr = ",".join(lang)
				while alchp == False:
					r = self.request(f"{url["comick"]["api"]}/comic/{dataSerie["hid"]}/chapters?limit={alchplimit}&page={alchppage}&lang={langStr}&chap-order=1")
					chp = r["json"]
					allChapter.extend([{
							"id":c['hid'], 
							"volume":c["vol"], 
							"chapter":c["chap"], 
							"title":c["title"], 
							"lang_short":c["lang"],
							"group":",".join([g["md_groups"]["title"] for g in c["md_chapters_groups"]] if len(c["md_chapters_groups"])>0 else c["group_name"]),
							"groupid":",".join([g["md_groups"]["slug"] for g in c["md_chapters_groups"]] if len(c["md_chapters_groups"])>0 else [g.replace(" ","-") for g in c["group_name"]]),
							"group_combid":[{"id":g["md_groups"]["slug"],"name":g["md_groups"]["title"],"fake":"0"} for g in c["md_chapters_groups"]] if len(c["md_chapters_groups"])>0 else [{"id":g.replace(" ","-"),"name":g,"fake":"1"} for g in c["group_name"]]
						} for c in chp["chapters"]])
					if len(allChapter) == chp["total"]:
						alchp = True
					else:
						alchppage=alchppage+1
					progress.update(id, {"status": "getting chapter info", "progress": str(round((len(allChapter)/chp["total"])*100,2)), "subprogress": "0"})
					time.sleep(1)

			for i,chp in enumerate(allChapter, start=1):
				progress.update(id, {"status": f"parse chapter info {i}/{len(allChapter)}", "progress": str(round((i/len(allChapter))*100,2)), "subprogress": "0"})
				data = {}
				data["id"] = chp["id"]
				data["serie"] = dataSerie["serie"]
				data["volume"] = chp["volume"]
				data["chapter"] = chp["chapter"]
				data["title"] = chp["title"]
				data["lang_short"] = chp["lang_short"]
				data["group"] = chp["group"]
				data["groupid"] = chp["groupid"]

				group = chp["group_combid"]
				groupDB = [gdb["id"] for gdb in queryDB(select=["id"],table=["tgroup"],where={"id":[g["id"] for g in group]},whereopt="or")]
				for g in group:
					if g["id"] not in groupDB:
						insereplaceDB(table=["tgroup"],values={"id":g["id"], "name":g["name"], "ignore":"0", "fake":g["fake"], "deleted":"0"})
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
					chp = queryDB(select=["id","got"],table=["chapter"],where={"id":p["data"]["id"]})
					if len(chp) > 0 and p["data"]["id"] == chp[0]["id"] and chp[0]["got"] == True:
						p["data"]["downloaded"] = True
					elif len(chp) > 0 and p["data"]["id"] == chp[0]["id"] and chp[0]["got"] == False:
						p["data"]["downloaded"] = False
					else:
						p["data"]["downloaded"] = False
						insereplaceDB(table=["chapter"], values={"id":p["data"]["id"], "series":dataSerie["id"], "title":p["data"]["title"] if p["data"]["title"] is not None else "", "volume":p["data"]["volume"] if p["data"]["volume"] is not None else "", "chapter":p["data"]["chapter"], "tgroup":p["data"]["groupid"] if "groupid" in p["data"] else "", "language":p["data"]["lang_short"], "time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "got":"0"})
					manga.append(p)
			progress.update(id, {"status": "got all chapter info", "progress": "100", "subprogress": "100"})
			return manga
		return {}

	def downloadToLestest(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
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

		mangadb = queryDB(select=["id","title","chapter","volume","tgroup","language","time","got"],table=["chapter"],where={"series":id})
		seriedb = queryDB(select=["source","h"],table=["series"],where={"id":id})
		serie = {}
		if len(seriedb) > 0:
			if seriedb[0]["source"] != "" and seriedb[0]["source"] in provider:
				serie = self.getSerieInfo({"id":id,"provider":seriedb[0]["source"]})
			else:
				serie = self.getSerieInfo({"id":id,"provider":"mangadex"})
			location = settings["saveHDir"] if seriedb[0]["h"]==True else settings["saveDir"]
			format = settings["hSaveName"] if seriedb[0]["h"]==True else settings["saveName"]
			progress.update(id, {"status": "downloading", "progress": "0", "subprogress": "0"})
			for i,m in enumerate(mangadb, start=1):
				progress.update(id, {"status": f"downloading {i}/{len(mangadb)}", "progress": str(round((i/len(mangadb))*100,2)), "subprogress": "0"})
				if m["got"] == False:
					if serie["provider"] == "mangadex":
						r = self.request(f"{url["mangadex"]["api"]}/at-home/server/{m["id"]}")
						chp = r["json"]
						m["serie"] = serie["serie"]
						g = queryDB(select=["name"],table=["tgroup"],where={"id":m["tgroup"]})
						m["group"] = g[0]["name"] if g and g[0]["name"] != None else ""
						m["authors_artists"] = ",".join(serie["author"] + serie["artist"])
						m["volume"] = m["volume"] if m["volume"] is not None else "0"
						m["chapter"] = m["chapter"] if m["chapter"] is not None else "0"
						m["title"] = m["title"] if m["title"] is not None else ""
						m["lang_short"] = m["language"]
						m = {**serie, **m}

						for j,p in enumerate(chp["chapter"]["data"], start=1): 
							progress.update(id, {"status": f"downloading {i}/{len(mangadb)} page {j}/{len(chp["chapter"]["data"])}", "progress": str(round((i/len(mangadb))*100,2)), "subprogress": str(round((j/len(chp["chapter"]["data"]))*100,2))})
							m["page"] = str(j)
							m["extension"] = os.path.splitext(p)[1]
							m["time"] = datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
							r = self.downloadPage(f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}", self.custom_format(location+format, **m))
							report = {
								"url": f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}",
								"success": True if r["status"] == 200 else False,
								"bytes": r["size"] if r["status"] == 200 else 0,
								"duration": round(r["usedtime"] * 1000),
								"cached": True if r["status"] == 200 else False
							}
							urllib.request.Request("https://api.mangadex.network/report", data=urllib.parse.urlencode(report).encode(), headers=headersPost)
							if r["status"] != 200:
								self.logged(f"Download {m["serie"]} - chapter {m['chapter']} failed. (page:{j} url:{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p})")
								break
						else:
							updateDB(table=["chapter"], values={"got":1}, where={"id":m["id"]})
							self.logged(f"Download {m["serie"]} - chapter {m['chapter']} success.")

					elif serie["provider"] == "comick":
						r = self.request(f"{url["comick"]["api"]}/chapter/{m["id"]}/get_images")
						chp = json.loads(r["data"])
						m["serie"] = serie["serie"]
						g = queryDB(select=["name"],table=["tgroup"],where={"id":m["tgroup"]})
						m["group"] = g[0]["name"] if g and g[0]["name"] != None else ""
						m["authors_artists"] = ",".join(serie["author"] + serie["artist"])
						m["volume"] = m["volume"] if m["volume"] is not None else "0"
						m["chapter"] = m["chapter"] if m["chapter"] is not None else "0"
						m["title"] = m["title"] if m["title"] is not None else ""
						m["lang_short"] = m["language"]
						m = {**serie, **m}

						for j,p in enumerate(chp, start=1): 
							progress.update(id, {"status": f"downloading {i}/{len(mangadb)} page {j}/{len(chp)}", "progress": str(round((i/len(mangadb))*100,2)), "subprogress": str(round((j/len(chp))*100,2))})
							m["page"] = str(j)
							m["extension"] = os.path.splitext(p["b2key"])[1]
							m["time"] = datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
							r = self.downloadPage(f"{url["comick"]["image"]}/{p["b2key"]}", self.custom_format(location+format, **m))
							if r["status"] != 200:
								self.logged(f"Download {m["serie"]} - chapter {m['chapter']} failed. (page:{j} url:{url["comick"]["image"]}/{p["b2key"]})")
								break
						else:
							updateDB(table=["chapter"], values={"got":1}, where={"id":m["id"]})
							self.logged(f"Download {m["serie"]} - chapter {m['chapter']} success.")

				progress.update(id, {"status": f"download {i}/{len(mangadb)}", "progress": str(round((i/len(mangadb))*100,2)), "subprogress": "0"})
			self.logged(f"Download {serie["serie"]} success.")
			progress.update(id, {"status": "download all", "progress": "100", "subprogress": "100"})
			return mangadb

	def downloadPage(self,url,location):
		out = {}
		if location != "" and url != "":
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
		status = ""
		if markVal in ["0","1"]:
			serie = queryDB(select=["id"],table=["series"],where={"id":serieid})
			if serie and serieid == serie[0]["id"]:
				updateDB(table=["series"], values={"h":markVal}, where={"id":serieid})
				status = "Saved"
			else:
				status = "No match serie"
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
						r["json"] = json.loads(r["data"])
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
		time = datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
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
		seriedb = queryDB(select=["id"],table=["series"],where={"id":settings["appBGCover"]})
		if settings["appBGType"] == "cover" and seriedb and settings["appBGCover"] == seriedb[0]["id"]:
			return self.getCover({"id":settings["appBGCover"]})
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
					"req":False,
					"def":False
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

		data = queryDB(select=["image"],table=["series"],where={"id":args["id"]})
		if data:
			return data[0]["image"]
		elif args["provider"] in provider:
			return self.getSerieInfo({"id":args["id"],"provider":args["provider"]})["cover"]

	def updateCover(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"id",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		manga = queryDB(select=["id","source"],table=["series"],where={"id":args["id"]})
		if manga and args["id"] == manga[0]["id"]:
			progress.update(args["id"], {"status": "downloading cover", "progress": 0, "subprogress": 0})
			data = self.getSerieInfo({"id":args["id"],"provider":manga[0]["source"]})
			data["extension"] = data["cover_extension"]
			data["artist"] = data["artist_string"]
			data["author"] = data["author_string"]
			progress.update(args["id"], {"status": "downloaded cover", "progress": 30, "subprogress": 100})

			progress.update(args["id"], {"status": "saving cover to db", "progress": 40, "subprogress": 0})
			updateDB(values={"imageName":data["cover_id"], "image":data["cover"]},table=["series"],where={"id":data["id"]})
			progress.update(args["id"], {"status": "saved cover to db", "progress": 60, "subprogress": 100})

			if settings["saveCover"] == "yes":
				progress.update(args["id"], {"status": "saving cover to file", "progress": 80, "subprogress": 0})
				format = settings["coverDir"]
				lo = settings["saveDir"]

				h = queryDB(select=["h"],table=["series"],where={"id":args["id"]})
				if h and h[0]["h"] == "1":
					format = settings["coverHDir"]
					lo = settings["saveHDir"]
				lo = self.custom_format(lo+format, **data)
				
				os.makedirs(os.path.dirname(lo),exist_ok=True)
				with open(lo, "wb") as file:
					file.write(data["cover"])
				self.logged(f"Cover saved as {lo}")
				progress.update(args["id"], {"status": "saved cover to file", "progress": 100, "subprogress": 100})

				return 1
			else:
				return 0
		else:
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
			fname = queryDB(select=["forceName","name"],table=["series"],where={"id":args["id"]})
			if fname and fname[0]["name"] != out["serie_original"]:
				updateDB(values={"name":out["serie_original"]},table=["series"],where={"id":args["id"]})
				logged(f"Change serie name from \"{fname[1]}\" to \"{out["serie_original"]}\"")
			if fname and fname[0]["forceName"] != None:
				out["serie"] = fname[0]["forceName"]
				out["serie_force"] = fname[0]["forceName"]

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

			r = self.request(f"{url["mangadex"]["image"]}/covers/{args["id"]}/{out["cover_full_name"]}")
			out["cover"] = r["data"]

		elif args["provider"] == "comick":
			r = self.request(f"{url["comick"]["api"]}/comic/{args["id"]}/?tachiyomi=true")
			manga = r["json"]
			out["provider"] = args["provider"]
			out["id"] = args["id"]
			out["hid"] = manga["comic"]["hid"]
			out["lastUpdate"] = None
			out["author"] = []
			out["artist"] = []
			out["serie_original"] = manga["comic"]["title"]
			out["serie"] = manga["comic"]["title"]
			out["serie_force"] = None
			fname = queryDB(select=["forceName","name"],table=["series"],where={"id":args["id"]})
			if fname and fname[0]["name"] != out["serie_original"]:
				updateDB(values={"name":out["serie_original"]},table=["series"],where={"id":args["id"]})
				logged(f"Change serie name from \"{fname[1]}\" to \"{out["serie_original"]}\"")
			if fname and fname[0]["forceName"] != None:
				out["serie"] = fname[0]["forceName"]
				out["serie_force"] = fname[0]["forceName"]

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

			r = self.request(f"{url["comick"]["image"]}/{out["cover_id"]}")
			out["cover"] = r["data"]

		return out

	def setForceName(self,value):
		value = json.loads(value)
		id = value["id"]
		name = value["name"] if value["name"] != "" else None
		updateDB(values={"forceName":name},table=["series"],where={"id":id})
		return 1

	def checkAllSeriesChapter(self):
		series = queryDB(select=["id","name","source"],table=["series"])
		for s in series:
			if s["source"] in provider:
				manga = self.getChapterInfoToLestest({"id":s["id"],"provider":s["source"]})
				if manga and len(manga) > 0:
					for m in manga:
						if m["data"]["downloaded"] == False:
							return {"id":s["id"],"provider":s["source"]}
				else:
					continue
		return 1

	def downloadChapter(self,args):
		checkInput = checkArg({
			"input":args,
			"context":[
				{
					"var":"id",
					"type":str,
					"req":True
				},
				{
					"var":"serie",
					"type":str,
					"req":True
				}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		id = args["id"]
		chapterdb = queryDB(select=["series","id","title","chapter","volume","tgroup","language","time","got"],table=["chapter"],where={"id":id})
		seriedb = queryDB(select=["id","name","forceName","author","artist","h","source"],table=["series"],where={"id":chapterdb[0]["series"]})
		if chapterdb and chapterdb[0]["id"] == id and seriedb and seriedb[0]["id"] == chapterdb[0]["series"]:
			if seriedb[0]["source"] in provider:
				location = settings["saveHDir"] if seriedb[0]["h"]==True else settings["saveDir"]
				format = settings["hSaveName"] if seriedb[0]["h"]==True else settings["saveName"]
				chapter = {}
				chapter["provider"] = seriedb[0]["source"]
				chapter["author"] = ",".join([a["name"] for a in queryDB(select=["name"],table=["author"],where={"id":seriedb[0]["author"].split(",")})]) if seriedb[0]["author"] != "" else ""
				chapter["artist"] = ",".join([a["name"] for a in queryDB(select=["name"],table=["author"],where={"id":seriedb[0]["artist"].split(",")})]) if seriedb[0]["artist"] != "" else ""
				chapter["authors_artists"] = ",".join(filter(None, [chapter["author"], chapter["artist"]]))
				chapter["serie_original"] = seriedb[0]["name"]
				chapter["serie_force"] = seriedb[0]["forceName"] if seriedb[0]["forceName"] != None else ""
				chapter["serie"] = seriedb[0]["name"] if seriedb[0]["forceName"] == None else seriedb[0]["forceName"]
				chapter["volume"] = chapterdb[0]["volume"] if chapterdb[0]["volume"] is not None else "0"
				chapter["chapter"] = chapterdb[0]["chapter"] if chapterdb[0]["chapter"] is not None else "0"
				chapter["title"] = chapterdb[0]["title"] if chapterdb[0]["title"] is not None else ""
				chapter["lang_short"] = chapterdb[0]["language"]
				
				if chapter["provider"] == "mangadex":
					r = self.request(f"{url["mangadex"]["api"]}/at-home/server/{chapterdb[0]["id"]}")
					chp = r["json"]
					for j,p in enumerate(chp["chapter"]["data"], start=1):
						progress.update(chapterdb[0]["series"], {"status": f"downloading chapter {chapterdb[0]['chapter']} page {j}/{len(chp['chapter']['data'])}", "progress": "0", "subprogress": str(round((j/len(chp['chapter']['data']))*100,2))})
						chapter["page"] = str(j)
						chapter["extension"] = os.path.splitext(p)[1]
						chapter["time"] = datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
						r = self.downloadPage(f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}", self.custom_format(location+format, **chapter))
						report = {
							"url": f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{p}",
							"success": True if r["status"] == 200 else False,
							"bytes": r["size"],
							"duration": round(r["usedtime"] * 1000),
							"cached": True if r["status"] == 200 else False
						}
						urllib.request.Request("https://api.mangadex.network/report", data=urllib.parse.urlencode(report).encode(), headers=headersPost)
						if r["status"] != 200:
							self.logged(f"Download {chapter['serie']} - chapter {chapter['chapter']} failed. (page:{j} url:{chp['baseUrl']}/data/{chp['chapter']['hash']}/{p})")
							break
					else:
						updateDB(table=["chapter"], values={"got":1}, where={"id":chapterdb[0]["id"]})
						self.logged(f"Download {chapter['serie']} - chapter {chapter['chapter']} success.")
						progress.update(chapterdb[0]["series"], {"status": f"download chapter {chapterdb[0]['chapter']}", "progress": "100", "subprogress": "100"})
						return 1
				
				elif chapter["provider"] == "comick":
					r = self.request(f"{url["comick"]["api"]}/chapter/{chapterdb[0]["id"]}/get_images")
					chp = r["json"]
					for j,p in enumerate(chp, start=1):
						progress.update(chapterdb[0]["series"], {"status": f"downloading chapter {chapterdb[0]['chapter']} page {j}/{len(chp)}", "progress": "0", "subprogress": str(round((j/len(chp))*100,2))})
						chapter["page"] = str(j)
						chapter["extension"] = os.path.splitext(p["b2key"])[1]
						chapter["time"] = datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')
						r = self.downloadPage(f"{url["comick"]["image"]}/{p["b2key"]}", self.custom_format(location+format, **chapter))
						if r["status"] != 200:
							self.logged(f"Download {chapter['serie']} - chapter {chapter['chapter']} failed. (page:{j} url:{url['comick']['image']}/{p['b2key']})")
							break
					else:
						updateDB(table=["chapter"], values={"got":1}, where={"id":chapterdb[0]["id"]})
						self.logged(f"Download {chapter['serie']} - chapter {chapter['chapter']} success.")
						progress.update(chapterdb[0]["series"], {"status": f"download chapter {chapterdb[0]['chapter']}", "progress": "100", "subprogress": "100"})
						return 1
		return 0


