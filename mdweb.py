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
from mdbase import clients,scriptLocation,config,userList,progress,configFile,logged,checkDB,verifyPassword
from mdmain import MDMain

svAddress = config["host"]
svPort = config["port"]
svCert = config["ssl_crt_location"]
svCertKey = config["ssl_key_location"]
SECRET_KEY = config["secret"]
TOKEN_VALID_TIME = config["token_valid_time"]

def base64url_encode(data):
	return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data):
	padding = '=' * (4 - len(data) % 4)
	return base64.urlsafe_b64decode(data + padding)

def generate_token(username, client_ip, user_agent):
	header = {"alg": "HS256", "typ": "JWT"}
	payload = {
		"username": username,
		"exp": int(time.time()) + int(TOKEN_VALID_TIME),
		"ip": client_ip,
		"ua": user_agent
	}

	header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
	payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
	signature = hmac.new(SECRET_KEY.encode('utf-8'), f"{header_b64}.{payload_b64}".encode('utf-8'), hashlib.sha256).digest()
	signature_b64 = base64url_encode(signature)

	return f"{header_b64}.{payload_b64}.{signature_b64}"

def verify_token(token, client_ip=None, user_agent=None):
	try:
		header_b64, payload_b64, signature_b64 = token.split('.')
		signature = base64url_decode(signature_b64)
		expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), f"{header_b64}.{payload_b64}".encode('utf-8'), hashlib.sha256).digest()

		if not hmac.compare_digest(signature, expected_signature):
			return False

		payload = json.loads(base64url_decode(payload_b64))
		if payload["exp"] < time.time():
			return False

		if config.get("strictlogin", 'false') == 'true':
			if payload.get("ip") != client_ip or payload.get("ua") != user_agent:
				return False
		
		return payload["username"]
	except Exception as e:
		logged(f"Token verification error: {e}")
		return False

def send_message(data, type="text", timestamp=datetime.fromisoformat(datetime.now().isoformat()).strftime('%Y-%m-%d %H:%M:%S')):
	out = {"timestamp": timestamp}
	if type == "json":
		out["type"] = "json"
		out["data"] = json.dumps(data)
	elif type == "progress":
		out["type"] = "progress"
		out["data"] = json.dumps(data)
	else:
		out["type"] = "text"
		out["data"] = data
	
	message = f"data: {json.dumps(out)}\n\n"
	message_bytes = message.encode('utf-8')
	
	for client in clients[:]:
		try:
			client.write(message_bytes)
			client.flush()
		except (BrokenPipeError, ConnectionResetError, ssl.SSLError) as e:
			logged(f"Error sending message to client: {str(e)}")
			if client in clients:
				clients.remove(client)
		except Exception as e:
			logged(f"Unexpected error sending message: {str(e)}")
			if client in clients:
				clients.remove(client)

class SecureHTTPRequestHandler(SimpleHTTPRequestHandler):
	def __init__(self, *args, **kwargs):
		self.web_dir = os.path.join(scriptLocation, 'web')
		super().__init__(*args, directory=self.web_dir, **kwargs)

	def send_header(self, keyword, value):
		if keyword.lower() in ['server', 'date', 'last-modified']:
			return
		super().send_header(keyword, value)

	def end_headers(self):
		super().send_header('Server', 'Mikan Web API')
		super().end_headers()

	def do_OPTIONS(self):
		self.send_response(200)
		self.send_header('Access-Control-Allow-Origin', '*')
		self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
		self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
		self.end_headers()

	def do_GET(self):
		if self.path in ['/web', '/web/index', '/web/index.htm', '/web/index.html', '/web/index.php', '/web/index.aspx']:
			self.send_response(302)
			self.send_header('Location', '/web/')
			self.end_headers()
			return

		if not self.path.startswith('/api') and not self.path.endswith('/') and self.path.count('.') == 0:
			logged(self.path)
			potential_dir = os.path.join(self.web_dir, self.path)
			logged(self.path)
			if os.path.isdir(potential_dir):
				self.send_response(302)
				logged(self.path)
				self.send_header('Location', self.path + '/')
				self.end_headers()
				return

		if self.path.startswith('/web/') and os.path.isfile(os.path.join(scriptLocation,"web",urlsplit(self.path).path[4:].replace("/../","/").lstrip("/") if urlsplit(self.path).path[4:].replace("/../","/").lstrip("/") != "" else "index.html")):
			self.path = self.path[4:]
			fpath = os.path.join(scriptLocation,"web",urlsplit(self.path).path.replace("/../","/").lstrip("/") if urlsplit(self.path).path.replace("/../","/").lstrip("/") != "" else "index.html")
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
			self.wfile.write(bytes(self.apiResponse()))
			return

		if not self.path.startswith('/api/login') and not self.authenticate():
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
			
			clients.append(self.wfile)
			try:
				send_message("New Client connected to log")
				progress.send(progress.to_dict())
				while True:
					try:
						self.wfile.write(b': keepalive\n\n')
						self.wfile.flush()
						time.sleep(30)
					except (BrokenPipeError, ConnectionResetError, ssl.SSLError) as e:
						logged(f"SSE connection error: {str(e)}")
						break
					except Exception as e:
						logged(f"Unexpected error in SSE: {str(e)}")
						break
						
			except (BrokenPipeError, ConnectionResetError) as e:
				logged(f"Client disconnected: {str(e)}")
			finally:
				if self.wfile in clients:
					clients.remove(self.wfile)
			return

		if self.path.startswith('/api'):
			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			self.wfile.write(bytes(json.dumps(self.apiResponse()), encoding='utf8'))
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
			
			if stored_password and verifyPassword(stored_password, password):
				token = generate_token(username, client_ip, user_agent)
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
		else:
			self.send_response(404)
			self.end_headers()
			self.wfile.write(b'{"error": "Not Found"}')

	def authenticate(self):
		auth_header = self.headers.get('Authorization')
		if not auth_header or not auth_header.startswith('Bearer '):
			return False

		token = auth_header.split(' ')[1]
		client_ip = self.client_address[0]
		user_agent = self.headers.get('User-Agent', '')
		username = verify_token(token, client_ip, user_agent)
		return username is not False

	def apiResponse(self):
		queryParams = parse_qs(urlparse(self.path).query)
		queryType = queryParams["type"] if "type" in queryParams else "na"
		queryText = " ".join(queryParams["value"]) if "value" in queryParams else ""
		queryStr = {}
		for q in queryParams:
			queryStr[q] = ",".join(queryParams[q])
		responseData = {
			"message": "api connect success.",
			"query_params": queryParams
		}
		mdmain = MDMain()
		mdmain.web = True
		if "ping" in queryType:
			responseData["data"] = "pong"
		elif "search" in queryType:
			responseData["data"] = mdmain.search(queryStr)
		elif "searchchapter" in queryType:
			responseData["data"] = mdmain.searchChapter(queryText)
		elif "knownseries" in queryType:
			responseData["data"] = mdmain.knownSeries()
		elif "knownserieschapter" in queryType:
			responseData["data"] = mdmain.knownSeriesChapter(queryText)
		elif "knowngroups" in queryType:
			responseData["data"] = mdmain.knownGroups()
		elif "knowngroupsset" in queryType:
			responseData["data"] = mdmain.knownGroupsset(queryText)
		elif "getsettings" in queryType:
			responseData["data"] = mdmain.getSettings()
		elif "updateserie" in queryType:
			responseData["data"] = mdmain.updateSerie(queryStr)
		elif "setsettings" in queryType:
			responseData["data"] = mdmain.setSettings(queryText)
		elif "addserie" in queryType:
			responseData["data"] = mdmain.addSerie(queryStr)
		elif "dllast" in queryType:
			responseData["data"] = mdmain.downloadToLestest(queryStr["id"])
		elif "updatechapter" in queryType:
			responseData["data"] = mdmain.getChapterInfoToLestest(queryStr)
		elif "updateanddllast" in queryType:
			mdmain.getChapterInfoToLestest(queryStr)
			responseData["data"] = mdmain.downloadToLestest(queryStr["id"])
		elif "updateforcename" in queryType:
			responseData["data"] = mdmain.setForceName(queryText)
		elif "updatecover" in queryType:
			responseData["data"] = mdmain.updateCover(queryStr)
		elif "dlchapter" in queryType:
			responseData["data"] = mdmain.downloadChapter(queryStr)
		elif "markh" in queryType:
			responseData["data"] = mdmain.markSerieH(queryText)
		elif "getcover" in queryType:
			responseData = mdmain.getCover(queryStr)
		elif "getbg" in queryType:
			responseData = mdmain.getAppBG()
		elif "progress" in queryType:
			responseData["data"] = progress.to_dict()

		global lastStatus
		if "restart" in queryType:
			lastStatus = "restart"
			threading.Thread(target=self.server.shutdown, daemon=True).start()
			responseData["data"] = {"status":"restarting"}
		elif "stop" in queryType:
			lastStatus = "stop"
			threading.Thread(target=self.server.shutdown, daemon=True).start()
			responseData["data"] = {"status":"stopping"}

		return responseData


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
	daemon_threads = True
	def restartServer(self):
		logged("Restart requested... shutting down.")
		
		def doRestart():
			self.shutdown()
			self.server_close()
			logged("Shutdown complete. Restarting now...")
			python = sys.executable
			os.execv(python, [python] + sys.argv)

		threading.Thread(target=doRestart, daemon=True).start()

def start_server():
	try:
		global lastStatus
		logged("Using config from: ", configFile)
		logged("database path: ", config["db_location"])
		logged("server address: ", svAddress)
		logged("server port: ", svPort)
		serverAddress = (svAddress, int(svPort))
		httpd = ThreadingHTTPServer(serverAddress, SecureHTTPRequestHandler)
		
		context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
		logged("certificate path: ", svCert)
		logged("certificate key path: ", svCert)
		context.load_cert_chain(certfile=svCert, keyfile=svCertKey)
		
		checkDB()
		
		httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
		def sendProgress(data):
			send_message(data,type="progress")
		progress.send = sendProgress
		mdmain = MDMain()
		mdmain.web = True
		logged("Server loaded!!!")
		logged(f"Serving on https://{svAddress}:{svPort}")

		def stopServer():
			logged("Stopping server...")
			httpd.shutdown()
			httpd.server_close()
			os._exit(0)

		def handleSignal(signum, frame):
			logged(f"Signal {signum} received. Shutting down...")
			threading.Thread(target=stopServer, daemon=True).start()

		signal.signal(signal.SIGINT, handleSignal)
		signal.signal(signal.SIGTERM, handleSignal)

		try:
			httpd.serve_forever()
		finally:
			httpd.server_close()
			if lastStatus == "restart":
				logged("Restarting server...")
				python = sys.executable
				os.execv(python, [python] + sys.argv)
			elif lastStatus == "stop":
				logged("Stopping server...")
				os._exit(0)

	except OSError as e:
		if e.errno == 98:
			logged(f"Error: Port {svPort} is already in use. Please try a different port or kill the process using this port.")
		else:
			logged(f"Error starting server: {e}")
		sys.exit(1)

if __name__ == '__main__':
	start_server()