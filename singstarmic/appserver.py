#!python3
import socket, time, logging, struct, enum
from datetime import datetime, timedelta

class Packet(enum.Enum):
	CONNECT               = 0
	DISCONNECT            = 1 # client -> server
	RTT                   = 2
	ACK                   = 3
	CONNECTION_CHALLENGE  = 4
	CONNECTION_CODE       = 5 # client -> server
	CONNECTION_SUCCESSFUL = 6
	ERROR                 = 7

	AUDIO                 = 256 # client -> server
	MIC_SET               = 257
	TIME_SYNC             = 258
	PERFORMANCE           = 259
	STATE_SELECTION       = 260
	PEERS_STATE           = 261
	CATALOGUE_REFRESH     = 262
	PLAYLIST_REFRESH      = 263
	MIC_STATE             = 264
	CURRENT_PLAYLIST      = 265
	TELEMETRY             = 266 # client -> server
	SESSION               = 267

class PeerState(enum.Enum):
	HOME     = -1
	MIC      = 1
	VFX      = 3
	PLAYLIST = 4

NO_ACK = [Packet.AUDIO, Packet.ACK]

class Player:
	ip = None
	sequence = 0
	pingTime = datetime.now()
	connectTime = datetime.now()

	microphoneNumber = None
	recordFile = None

	peerState = -1

class AppServer:
	IP = "0.0.0.0"
	PORT = 12000

	# Server state
	performanceState = 'disable'

	def __init__(self, micNo = 2):
		self.is_running = True
		self.players = {}
		self.micNo = micNo
		self.log = logging.getLogger(__name__)

	# PACKET FUNCTIONS
	def sendAll(self, function):
		for _, player in self.players.items():
			function(player)

	def sendAllPacket(self, cmd, packet = []):
		for _, player in self.players.items():
			self.send(player, cmd, packet)

	def sendKeepAlive(self, player):
		if (datetime.now() - player.pingTime).total_seconds() > 10:
			self.send(player, Packet.RTT)

	def sendPeerState(self, player):
		data = bytearray()
		slot = 0
		i = 0
		for _, p in self.players.items():
			if player.ip == p.ip:
				slot = i
			i += 1
			data += struct.pack('>i', p.peerState)
		self.send(player, Packet.PEERS_STATE, struct.pack('>BB', slot, len(self.players)) + data)

	def sendMicState(self, player):
		if self.performanceState == 'disable':
			return

		usedSlots = 0
		for _, p in self.players.items():
			if PeerState(p.peerState) is PeerState.MIC:
				usedSlots += 1
		self.send(player, Packet.MIC_STATE, struct.pack('>II', self.micNo - usedSlots, self.micNo))

	def send(self, player, cmd:Packet, data:list = []):
		self.log.debug("{0:s} send {1:s} ({2:04d}): {3:s}".format(player.ip, cmd.name, len(data), "".join("%02X " % b for b in data)))

		d = struct.pack('>III', 12 + len(data), cmd.value, player.sequence)
		d += bytes(data)

		if not cmd == Packet.ACK:
			player.sequence += 1
		player.pingTime = datetime.now()

		self.sock.sendto(d, (player.ip, 12000))

	# GAME FUNCTIONS
	def performance(self, state):
		self.performanceState = state
		if state == 'enable':
			self.log.info('Enabling performance')

			self.sendAllPacket(Packet.MIC_STATE, struct.pack('>II', len(self.players), 2))
			self.sendAllPacket(Packet.MIC_SET, struct.pack('>I', 0))

		elif state == 'disable':
			self.log.info('Disabling performance')
			self.sendAllPacket(Packet.MIC_STATE, struct.pack('>II', 0, 0))

		elif state == 'start':
			self.log.info('Starting performance')
			self.sendAllPacket(Packet.PERFORMANCE, [0])
			for _, player in self.players.items():
				player.recordFile = open('mic_' + player.ip + '.raw', 'wb')

		elif state == 'stop':
			self.log.info('Stopping performance')
			self.sendAllPacket(Packet.PERFORMANCE, [1])
			for _, player in self.players.items():
				if not player.recordFile is None and not player.recordFile.closed:
					player.recordFile.close()

	def play(self, entryId):
		self.log.info('Sending playing song %d', entryId)
		self.sendAllPacket(Packet.CURRENT_PLAYLIST, struct.pack('>I', entryId))

	def refreshCatalogue(self):
		self.sendAllPacket(Packet.CATALOGUE_REFRESH)

	def refreshPlaylist(self):
		self.sendAllPacket(Packet.PLAYLIST_REFRESH)

	# PLAYER FUNCTIONS
	def createPlayer(self, ip):
		player = Player()
		player.ip = ip
		self.players[ip] = player

		self.log.info('Player {0:s} entered the server!'.format(player.ip))

	def getPlayer(self, ip):
		if not ip in self.players:
			self.createPlayer(ip)
		return self.players[ip]


	# SERVER FUNCTIONS
	def stop(self):
		self.is_running = False

	def run(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setblocking(0)
		self.sock.bind((self.IP, self.PORT))

		while self.is_running:
			try:
				data, (ip, _) = self.sock.recvfrom(15000)
			except socket.error:
				time.sleep(0.001)
				self.sendAll(self.sendKeepAlive)
				continue

			# Handle packet
			player = self.getPlayer(ip)
			(pSize, pId, pSequence) = struct.unpack('>III', data[0:12])
			pId = Packet(pId)

			# ACK everything I receive that is not an ACK
			if not pId in NO_ACK:
				self.log.debug("{0:s} recv {1:s} ({2:04d}): {3:s}".format(player.ip, pId.name, pSize, "".join("%02X " % b for b in data[12:])))
				self.send(player, Packet.ACK)

			# Handle packets
			if pId == Packet.AUDIO:
				if not player.recordFile.closed:
					player.recordFile.write(bytearray(data[12+4+8+8+4:]))

			elif pId == Packet.DISCONNECT:
				self.log.info('Player {0:s} left the server!'.format(player.ip))
				del self.players[player.ip]

			elif pId == Packet.CONNECT:
				# Send challenge request
				# self.send(Packet.CONNECTION_CHALLENGE)
				# print("[+] Use connection code '0000'")
				self.send(player, Packet.CONNECTION_SUCCESSFUL, [1]) # Insta connect without challenge

			elif pId == Packet.CONNECTION_CODE:
				# Verify code
				self.send(player, Packet.CONNECTION_SUCCESSFUL, [1])

			elif pId == Packet.STATE_SELECTION:
				(player.peerState, ) = struct.unpack('>i', data[12:16])
				time.sleep(0.3)

				self.sendAll(self.sendPeerState)
				self.sendAll(self.sendMicState)

