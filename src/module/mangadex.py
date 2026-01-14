import os
import time
import re
from typing import Callable
import urllib.parse
from src.base import Base
from src.ModuleTemplate import ModuleTemplate

base = Base()
checkArg = base.checkArg
request = base.requestGet
queryDB = base.queryDB
updateDB = base.updateDB
insereplaceDB = base.insereplaceDB

class mangadex(ModuleTemplate):
	name = "mangadex"
	def __init__(self,logged:Callable|None=None,progress:Callable|None=None):
		self.logged = logged if logged != None else base.logged
		self.url = {
			"url": "https://www.mangadex.org",
			"api": "https://api.mangadex.org",
			"image": "https://uploads.mangadex.org",
			"report": "https://api.mangadex.network/report",
			"infoq": "includes[]=manga,cover_art,author,artist,tag,creator",
			"searchqd": {'includes[]':['cover_art,author'], 'order[relevance]':['desc'], 'contentRating[]':['safe','suggestive','erotica','pornographic']},
		}

	def search(self,keyword:str):
		checkInput = checkArg({
			"input":{"keyword":keyword},
			"context":[{"var":"keyword", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		out = []
		query = self.url["searchqd"]
		query["title"] = [keyword]
		url = urllib.parse.urlparse(self.url["api"])._replace(path="/manga",query=urllib.parse.urlencode(query,doseq=True))
		data = request(urllib.parse.urlunparse(url))["json"]["data"]
		for d in data:
			author = []
			artist = []
			data = {"serieid":d["id"], "name":"", "authorid":"", "author":"", "artistid":"", "artist":"", "provider":"mangadex"}
			for t in d["attributes"]["title"]:
				data["name"] = d["attributes"]["title"][t]
			for a in d["relationships"]:
				if a["type"] == "author":
					author.append(a["id"])
				if a["type"] == "artist":
					artist.append(a["id"])
			authordb = {a["id"]: a["name"] for a in queryDB(select=["id","name"],table=["author"],where={"id":author},whereopt="or")}
			artistdb = {a["id"]: a["name"] for a in queryDB(select=["id","name"],table=["author"],where={"id":artist},whereopt="or")}
			data["authorid"] = ", ".join(author)
			data["author"] = ", ".join([authordb[a] if a in authordb else "Unknown" for a in author])
			data["artistid"] = ", ".join(artist)
			data["artist"] = ", ".join([artistdb[a] if a in artistdb else "Unknown" for a in artist])
			out.append(data)
		return out

	def getSerieInfo(self,serieid:str):
		checkInput = checkArg({
			"input":{"id":serieid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		out = super().getSerieInfo(serieid)
		r = request(f"{self.url["api"]}/manga/{serieid}?{self.url["infoq"]}")
		manga = r["json"]["data"]
		out["provider"] = self.name
		out["id"] = serieid
		out["lastUpdate"] = re.sub(r'([+-]\d{2}:\d{2})$','',manga["attributes"]["updatedAt"].replace("T"," "))
		out["author"] = []
		out["artist"] = []
		out["serie_original"] = next(iter(manga["attributes"]["title"].values()))
		out["serie"] = out["serie_original"]
		out["serie_force"] = ""
		fname = queryDB(select=["forceName","name"],table=["series"],where={"id":serieid})
		if fname:
			out["serie"] = fname[0]["name"]
			if fname[0]["forceName"] != None and fname[0]["forceName"] != "":
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

		r = base.requestGet(f"{self.url["api"]}/cover/{out["cover_id"]}")
		out["cover_full_name"] = r["json"]["data"]["attributes"]["fileName"]
		out["cover_name"] = out["cover_full_name"].split(".")[0]
		out["cover_extension"] = "."+out["cover_full_name"].split(".")[1]

		r = base.requestGet(f"{self.url["image"]}/covers/{serieid}/{out["cover_full_name"]}")
		out["cover"] = r["data"]
		return out

	def getChapterList(self,serieid:str):
		checkInput = checkArg({
			"input":{"id":serieid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		alchp = False
		alchpoffset = 0
		alchplimit = 100
		alchptotal = 0
		allChapter = []
		lang = base.getInfo("settings")["languages"].split(",")

		query = {"limit":[alchplimit], "offset":[alchpoffset], "includes[]":["scanlation_group"], "contentRating[]":["safe","suggestive","erotica","pornographic"]}
		if len(lang) > 1:
			query["translatedLanguage[]"] = lang
		url = urllib.parse.urlparse(self.url["api"])._replace(path="/manga/"+serieid+"/feed")

		while alchp == False:
			query["offset"] = [alchpoffset]
			r = request(urllib.parse.urlunparse(url._replace(query=urllib.parse.urlencode(query,doseq=True))))
			chpdata = r["json"]
			alchptotal = int(chpdata["total"]) if "total" in chpdata else 0
			allChapter.extend([{
					"id": chp['id'], 
					"volume": chp["attributes"]["volume"], 
					"chapter": chp["attributes"]["chapter"], 
					"title": chp["attributes"]["title"], 
					"lang_short": chp["attributes"]["translatedLanguage"],
					"group": ",".join([g["attributes"]["name"] for g in chp["relationships"] if g["type"] == "scanlation_group"]),
					"groupid": ",".join([g["id"] for g in chp["relationships"] if g["type"] == "scanlation_group"]),
					"group_combid": [{"id":g["id"],"name":g["attributes"]["name"],"fake":"1" if g["attributes"]["official"] else "0"} for g in chp["relationships"] if g["type"] == "scanlation_group"]
				} for chp in chpdata["data"]])
			if len(allChapter) >= alchptotal:
				alchp = True
			else:
				alchpoffset=alchplimit+alchpoffset
				time.sleep(1)
		return allChapter

	def getAuthorInfo(self,authorid:str):
		checkInput = checkArg({
			"input":{"id":authorid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		out = super().getAuthorInfo(authorid)
		authordb = queryDB(select=["id"],table=["author"],where={"id":args["id"]})
		if len(authordb) > 0 and args["id"] == authordb[0]["id"]:
			return 0
		else:
			r = []
			r = base.requestGet(f"{self.url["api"]}/author/{args["id"]}")
			out["status"] = r["status"]
			if r["status"] == 200:
				data = r["json"]["data"]

				out["id"] = args["id"]
				out["name"] = data["attributes"]["name"]
			else:
				self.logged("[getAuthorInfo] not ok:",r["status"])
		return out

	def getChapterImg(self,chapterid:str):
		checkInput = checkArg({
			"input":{"id":chapterid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		def report(args):
			checkInput = base.checkArg({
				"input":args,
				"context":[
					{"var":"url", "type":str, "req":True},
					{"var":"status", "type":int, "req":True},
					{"var":"size", "type":int, "req":True},
					{"var":"usedtime", "type":int, "req":True},
					{"var":"cache", "type":str, "req":True}
				]
			})
			if checkInput["status"]=="success":
				reportData = {
					"url": args["url"],
					"success": True if args["status"] == 200 else False,
					"bytes": args["size"],
					"duration": round(args["usedtime"] * 1000),
					"cached": args["cache"].startswith("HIT")
				}
				r=base.requestPost("https://api.mangadex.network/report", data=reportData, logged=self.logged)
				if r["status"]!=200:
					self.logged("[mangadex] cannot report to server: ",r["status"])
			else:
				self.logged("[mangadex] cannot report to server: ",checkInput["data"]["msg"])

		imgList = []
		r = base.requestGet(f"{self.url["api"]}/at-home/server/{chapterid}")
		if r["status"]!=200 or r["json"]["result"]!="ok" or "chapter" not in r["json"]:
			self.logged(f"Get chapter {chapterid} images failed. (no data)")
			return []
		chp = r["json"]
		for page,name in enumerate(chp["chapter"]["data"], start=1):
			imgList.append({
				"page":page,
				"url":f"{chp["baseUrl"]}/data/{chp["chapter"]["hash"]}/{name}",
				"name":os.path.splitext(name)[0],
				"extension":os.path.splitext(name)[1],
				"callback": report
			})
		return imgList











