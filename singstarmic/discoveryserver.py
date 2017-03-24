#!python3
import socket, time, uuid, logging

class DiscoveryServer:
	IP = '0.0.0.0'
	PORT = 2155

	def __init__(self, name, id = None):
		self.is_running = True
		self.name = name
		self.id = id
		if self.id is None:
			self.id = str(uuid.uuid5(uuid.NAMESPACE_URL, '{0:d}/{1:s}/{2:d}'.format(uuid.getnode(), self.IP, self.PORT)))
		self.log = logging.getLogger(__name__)

	def stop(self):
		self.is_running = False

	def run(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setblocking(0)
		self.sock.bind((self.IP, self.PORT))

		self.log.info('Listening on {0:s}:{1:d}'.format(self.IP, self.PORT))
		self.log.debug('using host-id {0:s}'.format(self.id))

		while self.is_running:
			try:
				data, (ip, port) = self.sock.recvfrom(15000)
			except socket.error:
				time.sleep(0.01)
				continue

			# SingStar mic app sends "SRCH * HTTP/1.1\nST: device-discovery-protocol-version:00000000" (non standard HTTP request)
			message = 'HTTP/1.1 300 OK\n'
			message += 'host-name:{0:s}\n'.format(self.name)
			message += 'host-type:mic\n'
			message += 'host-request-port:{0:d}\n'.format(self.PORT)
			message += 'host-id:{0:s}\n'.format(self.id)

			self.log.debug('Sending server details to {0:s}:{1:d}'.format(ip, port))
			self.sock.sendto(message.encode('utf-8'), (ip, port))

# If running standalone
if __name__ == '__main__':
	logging.basicConfig(level=logging.INFO)
	server = DiscoveryServer('Karaoke Party!')
	try:
		server.run()
	except KeyboardInterrupt:
		pass
	server.stop()

