from collections.abc import Callable
import traceback
from functools import wraps
from src.base import Base, Log, View, Process

class MDMain:
	logged:Log|Callable = None
	def __init__(self, logged:Log|Callable=None) -> None:
		self.logged = logged if logged != None else Base().logged if isinstance(self.logged,Callable) != True else self.logged
		self.base = Base(self.logged)

	def __getattribute__(self, name):
		attr = super().__getattribute__(name)
		if callable(attr) and not name.startswith('__'):
			@wraps(attr)
			def wrapped(*args, **kwargs):
				try:
					return attr(*args, **kwargs)
				except Exception as e:
					self.logged(f"Error in {name}: {str(e)}")
					self.logged(traceback.format_exc())
					raise
			return wrapped
		return attr

	def search(self,args):
		return View(logged=self.logged).searchSerie(args)

	def knownSeriesChapter(self,serieid):
		return View(logged=self.logged).knownSeriesChapter({"id":serieid})

	def knownSeries(self):
		return View(logged=self.logged).knownSeries()

	def knownGroups(self):
		return View(logged=self.logged).knownGroups()

	def knownGroupsSet(self,args):
		return Process(logged=self.logged).markGroupsProp(args)

	def setSettings(self,value):
		return Process(logged=self.logged).setSettings(value)

	def getSettings(self):
		return View(logged=self.logged).getSettings()

	def addSerie(self,args):
		return Process(logged=self.logged).addSerie(args)

	def updateSerie(self,args):
		return Process(logged=self.logged).updateSerie(args)

	def addAuthor(self,args):
		return Process(logged=self.logged).addAuthor(args)

	def getChapterInfoToLestest(self,args):
		return Process(logged=self.logged).getChapterList(args)

	def downloadToLestest(self,args):
		return Process(logged=self.logged).downloadAllChapter(args)

	def markSerieH(self,args):
		return Process(logged=self.logged).markSerieProp(args)

	def getAppBG(self):
		return View(logged=self.logged).getAppBG()

	def getCover(self,args):
		return View(logged=self.logged).getCover(args)

	def updateCover(self,args):
		return Process(logged=self.logged).updateCover(args)

	def getSerieInfo(self,args):
		return View(logged=self.logged).getSerieInfo(args)

	def setForceName(self,args):
		return Process(logged=self.logged).markSerieProp(args)

	def checkAllSeriesChapter(self):
		return Process(logged=self.logged).getAllSeriesChapter()

	def downloadChapter(self,args):
		return Process(logged=self.logged).downloadChapter(args)

	def clearCache(self):
		return Process(logged=self.logged).clearCache()

	def clearQueue(self):
		return Process(logged=self.logged).clearQueue()

	def clearDoneQueue(self):
		return Process(logged=self.logged).clearDoneQueue()

	def processQueue(self,failed=False):
		return Process(logged=self.logged).processQueue(failed)

