from http.server import HTTPServer, SimpleHTTPRequestHandler
import signal
from socketserver import ThreadingMixIn
import ssl
import base64
import sys
import hashlib
import hmac
import os
import json
import threading
import time
from datetime import datetime
from urllib.parse import parse_qsl, urlparse, parse_qs, urlsplit
from mdmain import MDMain
from src.base import Base, Log, Progress

base = Base()
logc = Log()
logc.web = False
loggedLocal = logc.logged
config = base.getInfo("config")
userList = json.loads(base.getInfo("settings")["webUser"])
progress = base.getInfo("progress")
clientsLock = threading.Lock()
svAddress = config["host"]
svPort = config["port"]
svCert = config["ssl_crt_location"]
svCertKey = config["ssl_key_location"]
SECRET_KEY = config["secret"]
TOKEN_VALID_TIME = config["token_valid_time"]

def base64urlEncode(data):
	return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64urlDecode(data):
	padding = '=' * (4 - len(data) % 4)
	return base64.urlsafe_b64decode(data + padding)

def generateToken(username, client_ip, user_agent):
	header = {"alg": "HS256", "typ": "JWT"}
	payload = {
		"username": username,
		"exp": int(time.time()) + int(TOKEN_VALID_TIME),
		"ip": client_ip,
		"ua": user_agent
	}

	header_b64 = base64urlEncode(json.dumps(header).encode('utf-8'))
	payload_b64 = base64urlEncode(json.dumps(payload).encode('utf-8'))
	signature = hmac.new(SECRET_KEY.encode('utf-8'), f"{header_b64}.{payload_b64}".encode('utf-8'), hashlib.sha256).digest()
	signature_b64 = base64urlEncode(signature)

	return f"{header_b64}.{payload_b64}.{signature_b64}"

def verifyToken(token, client_ip=None, user_agent=None):
	try:
		header_b64, payload_b64, signature_b64 = token.split('.')
		signature = base64urlDecode(signature_b64)
		expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), f"{header_b64}.{payload_b64}".encode('utf-8'), hashlib.sha256).digest()

		if not hmac.compare_digest(signature, expected_signature):
			return False

		payload = json.loads(base64urlDecode(payload_b64))
		if payload["exp"] < time.time():
			return False

		if config.get("strictlogin", 'false') == 'true':
			if payload.get("ip") != client_ip or payload.get("ua") != user_agent:
				return False
		
		return payload["username"]
	except Exception as e:
		loggedLocal(f"Token verification error: {e}")
		return False

def sendMessage(data, msgType="text", timestamp=datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')):
	out = {"timestamp": timestamp}
	if msgType == "json":
		out["type"] = "json"
		out["data"] = json.dumps(data)
	elif msgType == "progress":
		out["type"] = "progress"
		out["data"] = json.dumps(data)
	else:
		out["type"] = "text"
		out["data"] = data

	message = f"data: {json.dumps(out)}\n\n"
	message_bytes = message.encode('utf-8')

	disconnectedClient = []
	
	with clientsLock:
		clients = base.getInfo("clients")[:]
	
	for client in clients:
		try:
			client_wfile = client['wfile']
			client_wfile.write(message_bytes)
			client_wfile.flush()
		except (BrokenPipeError, ConnectionResetError, ssl.SSLError) as e:
			loggedLocal(f"Client disconnected during send: {e.__class__.__name__}")
			disconnectedClient.append(client)
		except Exception as e:
			loggedLocal(f"Error sending message: {str(e)}")
			disconnectedClient.append(client)

	if disconnectedClient:
		with clientsLock:
			for client in disconnectedClient:
				if client in base.getInfo("clients"):
					base.getInfo("clients").remove(client)
					loggedLocal(f"Removed dead client. Remaining: {len(base.getInfo("clients"))}")

	return len(base.getInfo("clients"))


class SecureHTTPRequestHandler(SimpleHTTPRequestHandler):
	def __init__(self, *args, **kwargs):
		self.web_dir = os.path.join(base.getInfo("scriptLocation"), 'web')
		super().__init__(*args, directory=self.web_dir, **kwargs)

	def send_header(self, keyword, value):
		if keyword.lower() in ['server', 'date', 'last-modified']:
			return
		super().send_header(keyword, value)

	def end_headers(self):
		super().send_header('Server', 'Mikan Web API')
		super().end_headers()

	def do_GET(self):
		if self.path in ['/web', '/web/index', '/web/index.htm', '/web/index.html', '/web/index.php', '/web/index.aspx']:
			self.send_response(302)
			self.send_header('Location', '/web/')
			self.end_headers()
			return

		if not self.path.startswith('/api') and not self.path.endswith('/') and self.path.count('.') == 0:
			loggedLocal(self.path)
			potential_dir = os.path.join(self.web_dir, self.path)
			loggedLocal(self.path)
			if os.path.isdir(potential_dir):
				self.send_response(302)
				loggedLocal(self.path)
				self.send_header('Location', self.path + '/')
				self.end_headers()
				return

		if self.path.startswith('/web/') and os.path.isfile(os.path.join(base.getInfo("scriptLocation"),"web",urlsplit(self.path).path[4:].replace("/../","/").lstrip("/") if urlsplit(self.path).path[4:].replace("/../","/").lstrip("/") != "" else "index.html")):
			self.path = self.path[4:]
			fpath = os.path.join(base.getInfo("scriptLocation"),"web",urlsplit(self.path).path.replace("/../","/").lstrip("/") if urlsplit(self.path).path.replace("/../","/").lstrip("/") != "" else "index.html")
			self.send_response(200)
			self.send_header('Cache-Control', 'max-age=0, no-cache, no-store, must-revalidate')
			self.send_header('Pragma', 'no-store')
			self.send_header('Expires', 'Wed, 11 Jan 1984 05:00:00 GMT')
			try:
				f = open(fpath, 'rb')
				self.send_header("Content-type", self.guess_type(fpath))
				self.send_header("Content-Length", str(os.fstat(f.fileno())[6]))
				self.end_headers()
				self.copyfile(f, self.wfile)
				f.close()
				return 
			except OSError:
				self.end_headers()
				f.close()
				self.send_response(404)
				self.end_headers()
				self.wfile.write(b'{"error": "Not Found"}')
				return

		if self.path == '/':
			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			self.wfile.write(b'{"message": "Mikan web API"}')
			return

		if self.path.startswith('/api?type=getcover') or self.path.startswith('/api?type=getbg'):
			self.send_response(200)
			self.send_header('Content-type', 'image/*')
			self.send_header('Content-Disposition', 'inline; filename="'+(" ".join(parse_qs(urlparse(self.path).query)["value"]) if "value" in parse_qs(urlparse(self.path).query) else "cover")+'"')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			queryParams = parse_qs(urlparse(self.path).query)
			queryType = ",".join(queryParams["type"]) if "type" in queryParams else "na"
			queryStr = {}
			for q in queryParams:
				queryStr[q] = ",".join(queryParams[q])
			self.wfile.write(bytes(self.apiResponse(requestType=queryType,data=queryStr)))
			return

		if self.path.startswith('/api') and not self.authenticate():
			self.send_response(401)
			self.send_header('Content-type', 'application/')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			self.wfile.write(b'{"error": "Unauthorized"}')
			return

		if self.path == '/api/log':
			self.send_response(200)
			self.send_header('Content-type', 'text/event-stream')
			self.send_header('Cache-Control', 'no-cache, no-transform')
			self.send_header('Connection', 'keep-alive')
			self.send_header('X-Accel-Buffering', 'no')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			self.wfile.flush()
			
			client_info = {'wfile': self.wfile, 'addr': self.client_address}
			with clientsLock:
				base.getInfo("clients").append(client_info)
				loggedLocal(f"Client connected. Total clients: {len(base.getInfo("clients"))}")
			try:
				sendMessage("New Client connected to log")
				progress.send(progress.to_dict())
				keepalive_count = 0
				while True:
					try:
						self.wfile.write(b': keepalive\n\n')
						self.wfile.flush()
						keepalive_count += 1
						if keepalive_count % 5 == 0:
							try:
								self.wfile.write(b'')
								self.wfile.flush()
							except:
								break
						time.sleep(30)
					except (BrokenPipeError, ConnectionResetError, ssl.SSLError) as e:
						loggedLocal(f"SSE connection error: {e.__class__.__name__}")
						break
					except Exception as e:
						loggedLocal(f"Unexpected error in SSE: {str(e)}")
						break
			except (BrokenPipeError, ConnectionResetError) as e:
				loggedLocal(f"Client disconnected: {str(e)}")
			finally:
				with clientsLock:
					if client_info in base.getInfo("clients"):
						base.getInfo("clients").remove(client_info)
					loggedLocal(f"Client disconnected. Remaining clients: {len(base.getInfo("clients"))}")
			return

		queryParams = parse_qs(urlparse(self.path).query)
		queryType = ",".join(queryParams["type"]) if "type" in queryParams else "na"
		validType = ["ping","search","knownseries","knownserieschapter","knowngroups","getsettings","updateserie","setsettings","addserie","dllast","updatechapter","updateanddllast","updatecover","dlchapter","processqueue","processfailedqueue","stopqueue","clearqueue","cleardonequeue","clearcache","updateallserieschapter"]
		if self.path.startswith('/api') and self.authenticate() and queryType in validType:
			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			queryParams = parse_qs(urlparse(self.path).query)
			queryStr = {}
			for q in queryParams:
				queryStr[q] = ",".join(queryParams[q])
			self.wfile.write(bytes(json.dumps(self.apiResponse(requestType=queryType,data=queryStr)), encoding='utf8'))
			return
		else:
			self.send_response(404)
			self.end_headers()
			self.wfile.write(b'{"error": "Not Found"}')
			return

	def do_POST(self):
		if self.path == '/api/login':
			content_length = int(self.headers['Content-Length'])
			post_data = self.rfile.read(content_length).decode('utf-8')
			data = dict(parse_qsl(post_data))

			username = data.get('username')
			password = data.get('password')

			stored_password = userList.get(username)
			client_ip = self.client_address[0]
			user_agent = self.headers.get('User-Agent', '')
			
			if stored_password and base.verifyPassword(stored_password, password):
				token = generateToken(username, client_ip, user_agent)
				response_data = {"token": token}
				self.send_response(200)
				self.send_header('Content-type', 'application/json')
				self.send_header('Access-Control-Allow-Origin', '*')
				self.end_headers()
				self.wfile.write(bytes(json.dumps(response_data), 'utf-8'))
			else:
				self.send_response(401)
				self.send_header('Content-type', 'application/json')
				self.send_header('Access-Control-Allow-Origin', '*')
				self.end_headers()
				self.wfile.write(b'{"error": "Invalid credentials"}')
			return

		if self.path.startswith('/api') and not self.authenticate():
			self.send_response(401)
			self.end_headers()
			self.wfile.write(b'{"error": "Unauthorized"}')
			return

		queryParams = parse_qs(urlparse(self.path).query)
		queryType = ",".join(queryParams["type"]) if "type" in queryParams else "na"
		validType = ["updateforcename","markh","knowngroupsset"] 
		if self.path.startswith('/api') and self.authenticate() and queryType in validType:
			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf-8'))
			print(queryType)
			print(data)
			self.wfile.write(bytes(json.dumps(self.apiResponse(requestType=queryType,data=data)), encoding='utf8'))
			return
		else:
			self.send_response(404)
			self.end_headers()
			self.wfile.write(b'{"error": "Not Found"}')
			return

	def authenticate(self):
		auth_header = self.headers.get('Authorization')
		if not auth_header or not auth_header.startswith('Bearer '):
			return False

		token = auth_header.split(' ')[1]
		client_ip = self.client_address[0]
		user_agent = self.headers.get('User-Agent', '')
		username = verifyToken(token, client_ip, user_agent)
		return username is not False

	def apiResponse(self, requestType:str, data:dict):
		requestType = requestType.lower()
		responseData = {
			"message": "api connect success.",
			"type": requestType,
			"query": "data"
		}
		mdmain = MDMain()
		if "ping" == requestType:
			responseData["data"] = "pong"
		elif "search" == requestType:
			responseData["data"] = mdmain.search(data)
		elif "knownseries" == requestType:
			responseData["data"] = mdmain.knownSeries()
		elif "knownserieschapter" == requestType:
			responseData["data"] = mdmain.knownSeriesChapter(data["value"] if "value" in data else "")
		elif "knowngroups" == requestType:
			responseData["data"] = mdmain.knownGroups()
		elif "knowngroupsset" == requestType:
			responseData["data"] = mdmain.knownGroupsSet(data)
		elif "getsettings" == requestType:
			responseData["data"] = mdmain.getSettings()
		elif "updateserie" == requestType:
			responseData["data"] = mdmain.updateSerie(data)
		elif "setsettings" == requestType:
			responseData["data"] = mdmain.setSettings(data["value"] if "value" in data else "")
		elif "addserie" == requestType:
			responseData["data"] = mdmain.addSerie(data)
		elif "dllast" == requestType:
			responseData["data"] = mdmain.downloadToLestest(data)
		elif "updatechapter" == requestType:
			responseData["data"] = mdmain.getChapterInfoToLestest(data)
		elif "updateanddllast" == requestType:
			mdmain.getChapterInfoToLestest({**data, "toqueue":"yes"})
			responseData["data"] = mdmain.processQueue()
		elif "updateforcename" == requestType:
			responseData["data"] = mdmain.setForceName(data)
		elif "updatecover" == requestType:
			responseData["data"] = mdmain.updateCover(data)
		elif "dlchapter" == requestType:
			responseData["data"] = mdmain.downloadChapter(data)
		elif "markh" == requestType:
			responseData["data"] = mdmain.markSerieH(data)
		elif "getcover" == requestType.lower():
			responseData = mdmain.getCover(data)
		elif "getbg" == requestType:
			responseData = mdmain.getAppBG()
		elif "updateallserieschapter" == requestType:
			responseData = mdmain.checkAllSeriesChapter()
		elif "progress" == requestType:
			responseData["data"] = progress.to_dict()
		elif "processqueue" == requestType:
			responseData["data"] = mdmain.processQueue()
		elif "processfailedqueue" == requestType:
			responseData["data"] = mdmain.processQueue(failed=True)
		elif "stopqueue" == requestType:
			base.setQueueStop(True)
			responseData["data"] = {"status": "stop_requested"}
		elif "clearqueue" == requestType:
			responseData["data"] = mdmain.clearQueue()
		elif "cleardonequeue" == requestType:
			responseData["data"] = mdmain.clearDoneQueue()
		elif "clearcache"== requestType:
			responseData["data"] = mdmain.clearCache()

		global lastStatus
		if "restart" == requestType.lower():
			lastStatus = "restart"
			threading.Thread(target=self.server.shutdown, daemon=True).start()
			responseData["data"] = {"status":"restarting"}
		elif "stop" == requestType.lower():
			lastStatus = "stop"
			threading.Thread(target=self.server.shutdown, daemon=True).start()
			responseData["data"] = {"status":"stopping"}

		return responseData


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
	daemon_threads = True
	def restartServer(self):
		loggedLocal("Restart requested... shutting down.")
		
		def doRestart():
			self.shutdown()
			self.server_close()
			loggedLocal("Shutdown complete. Restarting now...")
			python = sys.executable
			os.execv(python, [python] + sys.argv)

		threading.Thread(target=doRestart, daemon=True).start()

def startServer():
	try:
		global lastStatus
		loggedLocal("Using config from: ", base.getInfo("configFile"))
		loggedLocal("database path: ", base.getInfo("config")["db_location"])
		loggedLocal("server address: ", svAddress)
		loggedLocal("server port: ", svPort)
		serverAddress = (svAddress, int(svPort))
		httpd = ThreadingHTTPServer(serverAddress, SecureHTTPRequestHandler)
		
		context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
		loggedLocal("certificate path: ", svCert)
		loggedLocal("certificate key path: ", svCertKey)
		context.load_cert_chain(certfile=svCert, keyfile=svCertKey)
		
		base.checkDB()
		
		httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
		Log.web = True
		Progress.web = True
		progress.send(progress.to_dict())
		loggedLocal("Server loaded!!!")
		loggedLocal(f"Serving on https://{svAddress if svAddress!="" else "0.0.0.0"}:{svPort}")

		def stopServer():
			loggedLocal("Stopping server...")
			httpd.shutdown()
			httpd.server_close()
			os._exit(0)

		def handleSignal(signum, frame):
			loggedLocal(f"Signal {signum} received. Shutting down...")
			threading.Thread(target=stopServer, daemon=True).start()

		signal.signal(signal.SIGINT, handleSignal)
		signal.signal(signal.SIGTERM, handleSignal)

		try:
			httpd.serve_forever()
		finally:
			httpd.server_close()
			if lastStatus == "restart":
				loggedLocal("Restarting server...")
				python = sys.executable
				os.execv(python, [python] + sys.argv)
			elif lastStatus == "stop":
				loggedLocal("Stopping server...")
				os._exit(0)

	except OSError as e:
		if e.errno == 98:
			loggedLocal(f"Error: Port {svPort} is already in use. Please try a different port or kill the process using this port.")
		else:
			loggedLocal(f"Error starting server: {e}")
		sys.exit(1)

if __name__ == '__main__':
	startServer()