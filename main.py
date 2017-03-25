import threading, signal, logging, shlex, traceback
from singstarmic.discoveryserver import DiscoveryServer
from singstarmic.appserver import AppServer
from singstarmic.catalogueserver import CatalogueServer

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class MicServer:
	is_running = False
	servers = {}

	def addServer(self, server):
		thread = threading.Thread(target=server.run)
		thread.name = server.__class__.__name__
		self.servers[thread.name.lower()] = (server, thread)
		return self

	def stop(self, signal = None, frame = None):
		self.is_running = False
		while self.servers:
			(_, (server, thread)) = self.servers.popitem()
			log.info('Stopping ' + thread.name)
			server.stop()
			thread.join()
		log.info('All servers stopped...')

	def command(self, text):
		lex = shlex.shlex(text.strip())
		lex.quotes = '"'
		lex.whitespace_split = True
		lex.commenters = ''
		arguments = list(lex)

		if len(arguments) > 0:
			# Check if we are targeting this or some other module
			target = self
			if arguments[0].lower() in self.servers:
				target = self.servers[arguments.pop(0).lower()][0]

			# Check if we have this command
			command = arguments.pop(0)
			if not hasattr(target, command):
				log.warning('Command `{0:s}` is not supported by module {1:s}'.format(command, target.__class__.__name__))
				return

			# Run command
			try:
				# Dangerous but mkai, PoC!
				arguments = [eval(argument) for argument in arguments]
				getattr(target, command)(*arguments)
			except Exception as e:
				log.error(e)

	def run(self):
		self.is_running = True

		# Run all servers
		for _, (_, thread) in self.servers.items():
			thread.start()

		# Run command loop
		log.info('All servers started')
		while self.is_running:
			self.command(input(''))
		log.info('Done')

	def exit(self):
		self.stop()


micServer = MicServer()
signal.signal(signal.SIGINT, micServer.stop)
try:
	discoveryServer = DiscoveryServer('Karaoke Party!')
	catalogueServer = CatalogueServer()
	appServer = AppServer()

	# Do some linking
	catalogueServer.onPlaylistChanged(appServer.refreshPlaylist)

	# Add all different server parts
	micServer.addServer(discoveryServer).addServer(catalogueServer).addServer(appServer)

	# Run the whole thing
	micServer.run()
except Exception as e:
	micServer.stop(None, None)
	if not isinstance(e, EOFError):
		log.exception("")
