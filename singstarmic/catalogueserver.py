#!python3
import http.server, socketserver, urllib, json, logging
# Notes
# - versionId has to be integer and can be used to check for client to submit older versions of a playlist
# - songId matches up with the catalogue
# - songId will be used to replace the albumUrl %d
# - state can be: played, nextup, queued, currentPlaying, none
# Catalogue
# {
# 	"albumUrl": "http://192.168.1.252:10422/img/%d",
# 	"songs": {
# 		"song-12" : {
# 			"artist": "Artist",
# 			"title": "Title"
# 		}
# 	}
# }
# Playlist
# {
# 	"versionId": "12",
# 	"array": [
# 		{
# 			"entryId": "12",
# 			"songId": "song-12",
# 			"state": "queued"
# 		}
# 	]
# }

class CatalogueServer:
	IP = '0.0.0.0'
	PORT = 10422

	img = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a\x00\x00\x00\x0d\x49\x48\x44\x52\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0a\x49\x44\x41\x54\x78\x9c\x63\x00\x01\x00\x00\x05\x00\x01\x0d\x0a\x2d\xb4\x00\x00\x00\x00\x49\x45\x4e\x44\xae\x42\x60\x82"

	catalogue = {
		'albumUrl': 'http://192.168.1.252:10422/img/%d',
		'songs': {
			'song-gorillaz-humanz-ascension': {
				'artist': 'Gorillaz',
				'title': 'Ascension feat. Vince Staples',
			},
			'song-gorillaz-humanz-strobelite': {
				'artist': 'Gorillaz',
				'title': 'Strobelite feat. Peven Everett',
			},
			'song-gorillaz-humanz-saturnz-barz': {
				'artist': 'Gorillaz',
				'title': 'Saturnz Barz feat. Popcaan',
			},
			'song-gorillaz-humanz-momentz': {
				'artist': 'Gorillaz',
				'title': 'Momentz feat. De La Soul',
			},
			'song-gorillaz-humanz-submission': {
				'artist': 'Gorillaz',
				'title': 'Submission feat. Danny Brown & Kelela',
			},
			'song-gorillaz-humanz-charger': {
				'artist': 'Gorillaz',
				'title': 'Charger feat. Grace Jones',
			},
			'song-gorillaz-humanz-andromeda': {
				'artist': 'Gorillaz',
				'title': 'Andromeda feat. D.R.A.M.',
			},
			'song-gorillaz-humanz-busted-and-blue': {
				'artist': 'Gorillaz',
				'title': 'Busted and Blue',
			},
			'song-gorillaz-humanz-carnival': {
				'artist': 'Gorillaz',
				'title': 'Carnival feat. Anthony Hamilton',
			},
			'song-gorillaz-humanz-let-me-out': {
				'artist': 'Gorillaz',
				'title': 'Let Me Out feat. Mavis Staples & Pusha T',
			},
			'song-gorillaz-humanz-sex-murder-party': {
				'artist': 'Gorillaz',
				'title': 'Sex Murder Party feat. Jamie Principle & Zebra Katz',
			},
			'song-gorillaz-humanz-shes-my-collar': {
				'artist': 'Gorillaz',
				'title': 'She’s My Collar feat. Kali Uchis',
			},
			'song-gorillaz-humanz-hallelujah-money': {
				'artist': 'Gorillaz',
				'title': 'Hallelujah Money feat. Benjamin Clementine',
			},
			'song-gorillaz-humanz-we-got-the-power': {
				'artist': 'Gorillaz',
				'title': 'We Got The Power feat. Jehnny Beth',
			},
		},
	}


	globalEntryId = 3
	playlist = {
		'versionId': 12,
		'array': [
			{
				'entryId': 1,
				'songId': 'song-gorillaz-humanz-ascension',
				'state': 'nextUp',
			},
			{
				'entryId': 0,
				'songId': 'song-gorillaz-humanz-strobelite',
				'state': 'currentPlaying',
			},
			{
				'entryId': 2,
				'songId': 'song-gorillaz-humanz-saturnz-barz',
				'state': 'none',
			},
		]
	}

	class Handler(http.server.BaseHTTPRequestHandler):
		parent = None
		def log_message(self, format, *args):
			self.parent.log.info(format, *args)

		def do_GET(self):
			if self.path == '/getCatalogue':
				self.send_response(200)
				self.send_header('Content-type','application/json')
				self.end_headers()

				self.wfile.write(json.dumps(self.parent.catalogue).encode('utf-8'))
			elif self.path == '/getPlaylist':
				self.send_response(200)
				self.send_header('Content-type','application/json')
				self.end_headers()

				self.wfile.write(json.dumps(self.parent.playlist).encode('utf-8'))
			elif self.path.startswith('/img/'):
				self.send_response(200)
				self.send_header('Content-type', 'image/png')
				self.end_headers()

				self.wfile.write(self.parent.img)
			else:
				self.send_response(404)
				self.end_headers()

		def do_POST(self):
			length = int(self.headers['Content-Length'])
			body = self.rfile.read(length).decode('utf-8')
			self.parent.log.debug('POST body' + body)

			# Handle the request
			if self.path == '/addPlaylist':
				songs = body.strip('[]').split(',')
				for song in songs:
					self.parent.playlist['array'].append({
						'entryId': self.parent.globalEntryId,
						'songId': song, # check if song exists
						'state': 'none'
					})
					self.parent.globalEntryId += 1

			elif self.path == '/orderPlaylist':
				data = json.loads(body)

				index = None
				for i, song in enumerate(self.parent.playlist['array']):
					if song['entryId'] == data['entryId']:
						index = i

				if not index is None:
					self.parent.playlist['array'].insert(index + data['offset'], self.parent.playlist['array'].pop(index))

			elif self.path == '/deletePlaylist':
				data = json.loads(body)

				# Find all the indices in the array that we want to remove given the entryId
				indices = [i for entryId in data['array'] for i, song in enumerate(self.parent.playlist['array']) if song['entryId'] == entryId]

				# Remove from self.parent.playlist
				for i in sorted(indices, reverse=True):
					del self.parent.playlist['array'][i]

				self.parent.playlist['versionId'] += 1

			# Just trigger callback
			if 'playlist' in self.parent.callbacks:
				self.parent.callbacks['playlist']()

			# POST responses are always just nothing
			self.send_response(200)
			self.send_header('Content-type','application/json')
			self.end_headers()

	def __init__(self,):
		self.callbacks = {}
		self.is_running = True
		self.log = logging.getLogger(__name__)

	def onPlaylistChanged(self, callback):
		self.callbacks['playlist'] = callback

	def stop(self):
		self.httpd.shutdown()

	def run(self):
		handler = self.Handler
		self.httpd = socketserver.TCPServer((self.IP, self.PORT), handler)
		handler.parent = self
		self.log.info('Listening on {0:s}:{1:d}'.format(self.IP, self.PORT))

		self.httpd.serve_forever()

# If running standalone
if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO)
	server = CatalogueServer()
	try:
		server.run()
	except KeyboardInterrupt:
		pass
	server.stop()
