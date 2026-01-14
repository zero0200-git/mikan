import argparse

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Mikan Cli Client"
	)
	parser.add_argument(
		"action",
		#help="action [known, search, add, updateanddownload, download, update, updatecover, setup, useradd, userreset, userdelete]"
		help="action [setup]"
	)
	""" parser.add_argument(
		"-s", "--serie",
		metavar="SERIEID",
		help="serie id"
	)
	parser.add_argument(
		"-n", "--name",
		metavar="SERIENAME",
		help="serie name"
	) """

	args = parser.parse_args()

	print(f"action: {args.action}")
	""" print(f"serie id: {args.serie}")
	print(f"serie name: {args.name}") """

	if args.action == "setup":
		print("\nMikan setup")
		import configparser
		import sqlite3
		from getpass import getpass
		from json import loads,dumps
		from src.base import Base

		configFile = Base().getInfo("configFile")
		settings = Base().getInfo("settings")
		print("\n")
		config = configparser.ConfigParser(interpolation=None)
		config.read(configFile)
		for confGroup in config:
			for confName in config[confGroup]:
				i = input("Please input \""+confGroup+" - "+confName+"\" Now is \""+config.get(confGroup, confName).replace("'","")+"\": ")
				config[confGroup][confName] = "'" + (i if i != "" else config.get(confGroup, confName).replace("'","")) + "'"
				print("save as \""+config.get(confGroup, confName).replace("'","")+"\"")
		with open(configFile, 'w') as configfile:
			config.write(configfile)

		print("\n")
		userAll = loads(settings["webUser"]) if settings["webUser"] != "" and settings["webUser"] != None and settings["webUser"] != "[]" else {}

		username = input("Please input Username: ")
		while(username in userAll):
			force = input("Already have this user, force reset Yes/No(default:No): ")
			if force.lower() == "yes" or force.lower() == "y":
				break
			else:
				username = input("Please input Username: ")
		password = Base().hashPassword(getpass("Please input Password: "))

		userAll[username] = password
		db = sqlite3.connect(Base().getInfo("config")["db_location"])
		db.execute('PRAGMA journal_mode=WAL;')
		cursor = db.cursor()
		cursor.execute("UPDATE `settings` SET `value` = ? WHERE key = ?", (dumps(userAll),"webUser",))
		db.commit()
		cursor.close()
		db.close()
