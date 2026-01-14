
from collections.abc import Callable

class ModuleTemplate:
	name = "moduleTemplate"
	def __init__(self, logged: Callable | None = None) -> None:
		self.url = {
			"url": "https://www.example.org",
			"api": "https://api.example.org",
			"image": "https://image.example.org"
		}

	def search(self, keyword:str) -> list:
		out = [{
			"serieid": "not-implemented",
			"name": "not-implemented",
			"authorid": "not-implemented, not-implemented",
			"author": "Unknown, Unknown",
			"artistid": "not-implemented, not-implemented",
			"artist": "Unknown, Unknown",
			"provider": self.name
		}]
		return out

	def getSerieInfo(self, serieid:str) -> dict:
		out = {
			"provider": self.name,
			"id": serieid,
			"lastUpdate": "1970-01-01 00:00:00",
			"author": ["not-implemented", "not-implemented"],
			"artist": ["not-implemented", "not-implemented"],
			"serie_original": "Unknown",
			"serie": "Unknown",
			"serie_force": "",
			"cover_id": "not-implemented",
			"author_string": "Unknown,Unknown",
			"artist_string": "Unknown,Unknown",
			"cover_full_name": "not-implemented.jpg",
			"cover_name": "not-implemented",
			"cover_extension": ".jpg",
			"cover": b""
		}
		return out

	def getAuthorInfo(self, authorid:str) -> dict:
		out = {
			"provider": self.name,
			"id": "not-implemented",
			"status": 200,
			"name": "not-implemented"
		}
		return out

	def getChapterImg(self, chapterid:str) -> list:
		out = [{
			"page": 1,
			"url": "not-implemented",
			"name": "not-implemented",
			"extension": ".jpg",
			"callback": lambda:"not-implemented"
		}]
		return out

	def getChapterList(self, serieid:str) -> list:
		out = [{
			"id": "not-implemented", 
			"volume": "0", 
			"chapter": "0", 
			"title": "Unknown", 
			"lang_short": "Unknown",
			"group": "Unknown,Unknown",
			"groupid": "not-implemented, not-implemented",
			"group_combid": [{
				"id": "not-implemented",
				"name": "Unknown",
				"fake": "1"
			}]
		}]
		return out