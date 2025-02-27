from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
import ssl
import base64
import sys
import hashlib
import hmac
import os
import json
import time
from urllib.parse import parse_qsl, urlparse, parse_qs
from mdmain import MDMain, readConfig

scriptLocation = os.path.abspath(os.path.dirname(sys.argv[0]))
config = readConfig()
svAddress = config["host"]
svPort = config["port"]
svCert = config["ssl_crt_location"]
svCertKey = config["ssl_key_location"]
SECRET_KEY = config["secret"]
TOKEN_VALID_TIME = config["token_valid_time"]

def hash_password(password):
	salt = os.urandom(16)
	pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
	return salt + pwdhash

def verify_password(stored_password, provided_password):
	salt = stored_password[:16] 
	stored_pwdhash = stored_password[16:]
	pwdhash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
	return hmac.compare_digest(stored_pwdhash, pwdhash)

USERS = {
	"admin": hash_password("mikan-admin")
}

def base64url_encode(data):
	return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data):
	padding = '=' * (4 - len(data) % 4)
	return base64.urlsafe_b64decode(data + padding)

def generate_token(username):
	header = {"alg": "HS256", "typ": "JWT"}
	payload = {
		"username": username,
		"exp": int(time.time()) + int(TOKEN_VALID_TIME)
	}

	header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
	payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
	signature = hmac.new(SECRET_KEY.encode('utf-8'), f"{header_b64}.{payload_b64}".encode('utf-8'), hashlib.sha256).digest()
	signature_b64 = base64url_encode(signature)

	return f"{header_b64}.{payload_b64}.{signature_b64}"

def verify_token(token):
	try:
		header_b64, payload_b64, signature_b64 = token.split('.')
		signature = base64url_decode(signature_b64)
		expected_signature = hmac.new(SECRET_KEY.encode('utf-8'), f"{header_b64}.{payload_b64}".encode('utf-8'), hashlib.sha256).digest()

		if not hmac.compare_digest(signature, expected_signature):
			return False

		payload = json.loads(base64url_decode(payload_b64))
		if payload["exp"] < time.time():
			return False

		return payload["username"]
	except Exception as e:
		print(f"Token verification error: {e}")
		return False

class SecureHTTPRequestHandler(SimpleHTTPRequestHandler):
	def __init__(self, *args, **kwargs):
		self.web_dir = os.path.join(scriptLocation, 'web')
		super().__init__(*args, directory=self.web_dir, **kwargs)

	def send_header(self, keyword, value):
		if keyword.lower() == 'server':
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
			print(self.path)
			potential_dir = os.path.join(self.web_dir, self.path)
			print(self.path)
			if os.path.isdir(potential_dir):
				self.send_response(302)
				self.send_header('Location', self.path + '/')
				print(self.path)
				self.end_headers()
				return

		if self.path.startswith('/web/'):
			self.path = self.path[4:]

			return super().do_GET()

		if self.path == '/':
			self.send_response(200)
			self.send_header('Content-type', 'application/json')
			self.send_header('Access-Control-Allow-Origin', '*')
			self.end_headers()
			self.wfile.write(b'{"message": "Welcome to the API!"}')
			return

		if self.path.startswith('/api?type=getcover'):
			self.send_response(200)
			self.send_header('Content-type', 'image/*')
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

			stored_password = USERS.get(username)
			if stored_password and verify_password(stored_password, password):
				token = generate_token(username)
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
		elif self.path.startswith('/api'):
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

	def authenticate(self):
		auth_header = self.headers.get('Authorization')
		if not auth_header or not auth_header.startswith('Bearer '):
			return False

		token = auth_header.split(' ')[1]
		username = verify_token(token)
		return username is not False

	def apiResponse(self):
		queryParams = parse_qs(urlparse(self.path).query)
		queryType = queryParams["type"] if "type" in queryParams else "na"
		queryText = " ".join(queryParams["value"]) if "value" in queryParams else ""

		responseData = {
			"message": "api connect success.",
			"query_params": queryParams
		}
		mdmain = MDMain()
		if "search" in queryType:
			responseData["data"] = mdmain.search(queryText)
		elif "searchchapter" in queryType:
			responseData["data"] = mdmain.searchChapter(queryText)
		elif "knownseries" in queryType:
			responseData["data"] = mdmain.knownSeries()
		elif "knownserieschapter" in queryType:
			responseData["data"] = mdmain.knownSeriesChapter(queryText)
		elif "getsettings" in queryType:
			responseData["data"] = mdmain.getSettings()
		elif "updateserie" in queryType:
			responseData["data"] = mdmain.updateSerie(queryText)
		elif "setsettings" in queryType:
			responseData["data"] = mdmain.setSettings(queryText)
		elif "addserie" in queryType:
			responseData["data"] = mdmain.addSerie(queryText)
		elif "addauthor" in queryType:
			responseData["data"] = mdmain.addAuthor(queryText)
		elif "dllast" in queryType:
			responseData["data"] = mdmain.downloadToLestest(queryText)
		elif "updateforcename" in queryType:
			responseData["data"] = mdmain.setForceName(queryText)
		elif "updatecover" in queryType:
			responseData["data"] = mdmain.updateCover(queryText)
		elif "getcover" in queryType:
			responseData = mdmain.getCover(queryText)

		return responseData

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
	pass

server_address = (svAddress, int(svPort))
httpd = ThreadingHTTPServer(server_address, SecureHTTPRequestHandler)

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile=svCert, keyfile=svCertKey)

httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

print("Server loaded!!!")
print("Serving on https://"+svAddress+":"+svPort)
httpd.serve_forever()