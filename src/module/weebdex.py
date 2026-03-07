from collections.abc import Callable
import os
import re
import time
import urllib.parse
from src.base import Base
from src.ModuleTemplate import ModuleTemplate


base = Base()
checkArg = base.checkArg
request = base.requestGet
queryDB = base.queryDB

class weebdex(ModuleTemplate):
	name = "weebdex"
	def __init__(self, logged: Callable | None = None) -> None:
		self.logged = logged if logged != None else base.logged
		self.url = {
			"url": "https://www.weebdex.org",
			"api": "https://api.weebdex.org",
			"image": "https://srv.weebdex.net",
			"searchqd": {'order[relevance]':['desc'], 'contentRating':['safe','suggestive','erotica','pornographic']},
		}

	def search(self, keyword:str) -> list:
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
			data = {"serieid":d["id"], "name":d["title"], "authorid":"Unknown", "author":"Unknown", "artistid":"unknown", "artist":"unknown", "provider":self.name}
			out.append(data)
		return out

	def getSerieInfo(self, serieid:str) -> dict:
		checkInput = checkArg({
			"input":{"id":serieid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		out = super().getSerieInfo(serieid)
		r = request(f"{self.url["api"]}/manga/{serieid}")
		manga = r["json"]
		out["provider"] = self.name
		out["id"] = serieid
		out["lastUpdate"] = re.sub(r'(\.\d+)?(Z|[+-]\d{2}:\d{2})$','',manga["updated_at"].replace("T"," "))
		out["author"] = []
		out["artist"] = []
		out["serie_original"] = manga["title"]
		out["serie"] = out["serie_original"]
		out["serie_force"] = ""
		fname = queryDB(select=["forceName","name"],table=["series"],where={"id":serieid,"source":self.name})
		if fname:
			out["serie"] = fname[0]["name"]
			if fname[0]["forceName"] != None and fname[0]["forceName"] != "":
				out["serie"] = fname[0]["forceName"]
				out["serie_force"] = fname[0]["forceName"]

		for a in manga["relationships"]["authors"]:
			out["author"].append(a["id"])
		for a in manga["relationships"]["artists"]:
			out["artist"].append(a["id"])
		out["author_string"] = ",".join(out["author"])
		out["artist_string"] = ",".join(out["artist"])
		out["cover_id"] = manga["relationships"]["cover"]["id"]
		out["cover_full_name"] = manga["relationships"]["cover"]["id"]+manga["relationships"]["cover"]["ext"]
		out["cover_name"] = manga["relationships"]["cover"]["id"]
		out["cover_extension"] = manga["relationships"]["cover"]["ext"]

		r = request(f"{self.url["image"]}/covers/{serieid}/{out["cover_full_name"]}")
		out["cover"] = r["data"]
		return out

	def getAuthorInfo(self, authorid:str) -> dict:
		checkInput = checkArg({
			"input":{"id":authorid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		args=checkInput["data"]["normal"]

		out = super().getAuthorInfo(authorid)
		authordb = queryDB(select=["id"],table=["author"],where={"id":args["id"],"source":self.name})
		if len(authordb) > 0 and args["id"] == authordb[0]["id"]:
			return 0
		else:
			r = []
			r = request(f"{self.url["api"]}/author/{args["id"]}")
			out["status"] = r["status"]
			if r["status"] == 200:
				data = r["json"]

				out["id"] = authorid
				out["name"] = data["name"]
				out["provider"] = self.name
			else:
				self.logged("[getAuthorInfo] not ok:",r["status"])
		return out

	def getChapterImg(self, chapterid:str) -> list:
		checkInput = checkArg({
			"input":{"id":chapterid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		imgGet = False
		imgList = []
		while imgGet == False:
			r = base.requestGet(f"{self.url["api"]}/chapter/{chapterid}")
			if r["status"] != 200:
				self.logged(f"Get chapter {chapterid} images failed. ({r["status"]})")
				return []
			chp = r["json"]
			for page,name in enumerate(chp["data"], start=1):
				imgList.append({
					"page": page,
					"url": f"{chp["node"]}/data/{chapterid}/{name["name"]}",
					"name": os.path.splitext(name["name"])[0],
					"extension": os.path.splitext(name["name"])[1]
				})
			imgGet = True
		return imgList

	def getChapterList(self, serieid:str) -> list:
		checkInput = checkArg({
			"input":{"id":serieid},
			"context":[{"var":"id", "type":str, "req":True}]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])

		alchp = False
		alchpoffset = 1
		alchplimit = 100
		alchptotal = 0
		allChapter = []
		lang = base.getInfo("settings")["languages"].split(",")

		query = {"limit":[alchplimit], "page":[alchpoffset]}
		if len(lang) > 1: query["tlang"] = lang
		url = urllib.parse.urlparse(self.url["api"])._replace(path="/manga/"+serieid+"/chapters")

		while alchp == False:
			query["page"] = [alchpoffset]
			r = request(urllib.parse.urlunparse(url._replace(query=urllib.parse.urlencode(query,doseq=True))))
			if r["status"] == 200:
				chpdata = r["json"]
				alchptotal = int(chpdata["total"]) if "total" in chpdata else 0
				for chp in chpdata["data"]:
					allChapter.extend([{
							"id": chp["id"],
							"volume": chp["volume"] if "volume" in chp else "0",
							"chapter": chp["chapter"] if "chapter" in chp else "0",
							"title": chp["title"] if "title" in chp else "",
							"lang_short": chp["language"],
							"group": ",".join([g["name"] for g in chp["relationships"]["groups"]]),
							"groupid": ",".join([g["name"] for g in chp["relationships"]["groups"]]),
							"group_combid": [{"id":g["id"],"name":g["name"],"fake":"0"} for g in chp["relationships"]["groups"]]
						}])
				if len(allChapter) >= alchptotal:
					alchp = True
				else:
					alchpoffset=alchpoffset+1
		return allChapter