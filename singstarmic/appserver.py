#!python3
import socket, time, logging, struct, enum
from datetime import datetime, timedelta

class Packet(enum.Enum):
	ID_CONNECT            = 0
	ID_DISCONNECT         = 1 # CLIENT -> SERVER
	ID_RTT                = 2
	ID_ACK                = 3
	CONNECTION_CHALLENGE  = 4
	CONNECTION_CODE       = 5 # CLIENT -> SERVER
	CONNECTION_SUCCESSFUL = 6

	ID_AUDIO              = 256 # CLIENT -> SERVER
	ID_MIC_SET            = 257
	ID_PERFORMANCE        = 259
	ID_STATE_SELECTION    = 260
	ID_PEERS_STATE        = 261
	ID_CATALOGUE_REFRESH  = 262
	ID_PLAYLIST_REFRESH   = 263
	MIC_STATE             = 264
	CURRENT_PLAYLIST      = 265
	TELEMETRY             = 266 # CLIENT -> SERVER
	SESSION               = 267

class PeerState(enum.Enum):
	HOME     = -1
	MIC      = 1
	VFX      = 3
	PLAYLIST = 4

NO_ACK = [Packet.ID_AUDIO, Packet.ID_ACK]

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
			self.send(player, Packet.ID_RTT)

	def sendPeerState(self, player):
		data = bytearray()
		slot = 0
		i = 0
		for _, p in self.players.items():
			if player.ip == p.ip:
				slot = i
			i += 1
			data += struct.pack('>i', p.peerState)
		self.send(player, Packet.ID_PEERS_STATE, struct.pack('>BB', slot, len(self.players)) + data)

	def sendMicState(self, player):
		usedSlots = 0
		for _, p in self.players.items():
			if PeerState(p.peerState) is PeerState.MIC:
				usedSlots += 1
		self.send(player, Packet.MIC_STATE, struct.pack('>II', self.micNo - usedSlots, self.micNo))


	def send(self, player, cmd:Packet, data:list = []):
		print("[*][{0:16s}] send {1:s} ({2:04d}):".format(player.ip, cmd.name, len(data)), "".join("%02X " % b for b in data))

		d = struct.pack('>III', 12 + len(data), cmd.value, player.sequence)
		d += bytes(data)

		if not cmd == Packet.ID_ACK:
			player.sequence += 1
		player.pingTime = datetime.now()

		self.sock.sendto(d, (player.ip, 12000))

	# GAME FUNCTIONS
	def performanceEnable(self):
		print("Enabling performance")
		self.sendAllPacket(Packet.MIC_STATE, struct.pack('>II', len(self.players), 2))
		self.sendAllPacket(Packet.ID_MIC_SET, struct.pack('>I', 0))

	def performanceDisable(self):
		print("Disabling performance")
		self.sendAllPacket(Packet.MIC_STATE, struct.pack('>II', 0, 0))

	def performanceStart(self):
		print("Starting performance")
		self.sendAllPacket(Packet.ID_PERFORMANCE, [0])
		for _, player in self.players.items():
			player.recordFile = open('mic_' + player.ip + '.raw', "wb")

	def performanceStop(self):
		print("Stopping performance")
		self.sendAllPacket(Packet.ID_PERFORMANCE, [1])
		for _, player in self.players.items():
			if not player.recordFile is None and not player.recordFile.closed:
				player.recordFile.close()

	def refreshCatalogue(self):
		self.sendAllPacket(Packet.ID_CATALOGUE_REFRESH)

	def refreshPlaylist(self):
		self.sendAllPacket(Packet.ID_PLAYLIST_REFRESH)

	# PLAYER FUNCTIONS
	def createPlayer(self, ip):
		player = Player()
		player.ip = ip
		self.players[ip] = player

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
				print("[*][{0:16s}] recv {1:s} ({2:04d}):".format(player.ip, pId.name, pSize), "".join("%02X " % b for b in data[12:]))
				self.send(player, Packet.ID_ACK)

			# Handle packets
			if pId == Packet.ID_AUDIO:
				if not player.recordFile.closed:
					player.recordFile.write(bytearray(data[12+4+8+8+4:]))

			elif pId == Packet.ID_DISCONNECT:
				print('[-] Player {0:s} left the game!'.format(player.ip))
				del self.players[player.ip]

			elif pId == Packet.ID_CONNECT:
				# Send challenge request
				# self.send(Packet.CONNECTION_CHALLENGE)
				# print("[+] Use connection code '0000'")
				self.send(player, Packet.CONNECTION_SUCCESSFUL, [1]) # Insta connect without challenge

			elif pId == Packet.CONNECTION_CODE:
				# Verify code
				self.send(player, Packet.CONNECTION_SUCCESSFUL, [1])

			elif pId == Packet.ID_STATE_SELECTION:
				(player.peerState, ) = struct.unpack('>i', data[12:16])
				time.sleep(0.3)

				self.sendAll(self.sendPeerState)
				self.sendAll(self.sendMicState)

