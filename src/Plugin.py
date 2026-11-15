from src.PluginTemplate import PluginTemplate
from src.checkarg import checkArg
from src.base import Base

class Plugin(PluginTemplate):
	def _getName(self):
		return self.name

	def _checkAuthor(self, args:dict) -> bool:
		checkInput = checkArg({
			"input":args,
			"context":[
				{"var":"authorid", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		input=checkInput["data"]["normal"]

		authordb = Base().queryDB(
			select=["author_ref.ext_id"],
			table=["author LEFT JOIN author_ref ON author.author_uid=author_ref.uid"],
			where={"author_ref.ext_id":input["authorid"], "author_ref.plugin":self.name}
		)
		out = False
		if len(authordb)>0: out = True
		return out

	def _getAuthorName(self, args:dict) -> str:
		checkInput = checkArg({
			"input":args,
			"context":[
				{"var":"authorid", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		input=checkInput["data"]["normal"]

		authordb = Base().queryDB(
			select=["author.name AS name"],
			table=["author_ref LEFT JOIN author ON author.uid=author_ref.author_uid"],
			where={"author_ref.ext_id":input["authorid"], "author_ref.plugin":self.name}
		)
		out = "Unknown"
		if len(authordb)>0: out = authordb[0]["name"]
		return out

	def _getSeriesName(self, args:dict) -> dict:
		checkInput = checkArg({
			"input":args,
			"context":[
				{"var":"seriesid", "type":str, "req":True}
			]
		})
		if checkInput["status"]=="failed": raise Exception(checkInput["data"]["msg"])
		input=checkInput["data"]["normal"]

		seriesdb = Base().queryDB(
			select=["series.name AS name","series.forceName AS forceName"],
			table=["series_ref LEFT JOIN series ON series.uid = series_ref.series_uid"],
			where={"series_ref.ext_id":input["seriesid"], "series_ref.plugin":self.name}
		)
		out = {"name":"","forceName":"","originalName":""}
		if len(seriesdb)>0:
			out["name"] = seriesdb[0]["name"]
			out["originalName"] = seriesdb[0]["name"]
			out["forceName"] = seriesdb[0]["forceName"]
			if seriesdb[0]["forceName"] != None and seriesdb[0]["forceName"] != "":
				out["name"] = seriesdb[0]["forceName"]
		return out