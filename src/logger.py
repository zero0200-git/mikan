
from datetime import datetime
import os
import sys
import traceback

class Log:
	web = False
	def logged(self, *value) -> None:
		value = list(value)
		for i in range(len(value)):
			value[i] = str(value[i])
		timeRun = datetime.now().isoformat()
		time = datetime.fromisoformat(timeRun).strftime("%Y-%m-%d %H:%M:%S")
		text = f"[{time}] {"".join(value)}"
		print(text)
		logDir = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), "log")
		logFile = logDir+"/"+datetime.fromisoformat(timeRun).strftime("%Y-%m-%d")+".log"
		if os.path.isdir(logDir) != True:
			os.makedirs(logDir,exist_ok=True)
		try:
			with open(logFile, "a", encoding="utf-8") as file:
				file.write(text+"\n")
			if self.web:
				from mdweb import sendMessage
				sendMessage("".join(value), timestamp=time)
		except Exception as e:
			print(traceback.format_exc())
			print(f"Error writing log to {logFile}: {e}")
	__call__ = logged