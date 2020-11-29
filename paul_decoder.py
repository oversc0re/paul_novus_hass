import serial
import binascii
import logging as log
import struct
import time
import sys
import threading
# Set display list to true to enable display of aggregated list of unique commands sent from the unit. (Requires TKinter)

display_list = False

if (display_list):
	import tkinter

log.basicConfig(
	stream=sys.stdout,
	format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
	level=log.INFO,
	datefmt='%S')



def crc16_ccitt(crc, data): 
    msb = crc >> 8
    lsb = crc & 255
    for c in data:
        # x = ord(c) ^ msb
        x = c ^ msb
        x ^= (x >> 4)
        msb = (lsb ^ (x >> 3) ^ (x << 4)) & 255
        lsb = (x ^ (x << 5)) & 255
    return (msb << 8) + lsb


class Paul():
	def __init__(self, serial_handle):
		# Configuration section
		self._known_commands = {'STATUS': 0x00, 'BROADCAST_REQUEST': 0x80, 'BROADCAST_ANSWER': 0x81, 'UNKNOWN':0x83, 'PING':0x84, 'GET_SET':0x85, 'ASK': 0x86, 'OTHER':0x87}
		self._addresses = { 'BROADCAST_0': b'\x00\x00', 'BROADCAST_1': b'\x01\x00', 'MASTER': b'\x01\x01',
							'UNKNWN1': b'\x01\x02', 'UNKNWN2': b'\x01\x03', 'MY_ADDR': b'\x01\x04', 'TFT2': b'\x01\x05',
							'WHATEVA': b'\x01\x06', 'UNKNWN3': b'\x01\x07', 'SLAVE': b'\x01\x08', 'UNKNWN4': b'\x01\x09',
							'UNKNWN5': b'\x01\x0a', 'UNKNWN6': b'\x01\x0b', 'UNKNWN7': b'\x01\x0c','UNKNWN8':  b'\x01\xFF'}
		self.subcmds = {'set_lang': 0x06, 'set_fan': 0x08, 'get_filter_time_left': 0x09, 'get_bypass':0x1A,
						'get_operating_hours': 0x26, 'get_temps':0x44}
		self._address_start_bytes = [b'\x00', b'\x01']
		self.__frame = {}
		self.__ask_data = b'\x00\x02\x03'
		self.__ping_data =b'\x41\x00\x00'
		self.__temp_keys = ['T1','T2','T3','T4']
		self._ser = serial_handle
		self._frames_list = [{}]
		self._start_time = time.time()

		self.filter_time_days = 0
		self.temp = []
		self.bypass = 0
		self.status = {}

	def __read(self, bytes_to_read):
		r = self._ser.read(bytes_to_read)
		# print (binascii.hexlify(r))
		return r

	def __write(self, data):
		log.debug("Writing> %s" % (binascii.hexlify(data)))
		self._ser.write(data)

		return

	def __novus_crc(self, data):
		crc = crc16_ccitt(0, data)
		# return bytearray.fromhex(crcHexStr)
		return crc


	def __validate_frame_crc(self):
		# refCrc = self.frame['raw'][4:6]
		crc = self.__novus_crc(self.__frame['raw'][0:4] + self.__frame['raw'][6:])
		if (crc != self.__frame['crc']):
			log.error("Invalid CRC cal:%d rx:%d -> %s" % (crc, self.__frame['crc'], binascii.hexlify(self.__frame['raw'])))
		return crc == self.__frame['crc']


	def __validate_frame_command(self):
		return self.__frame['cmd'] in self._known_commands.values()


	def __is_subcmd(self, subcmd_id):
		try:
			result = ((self.__frame["cmd"] == 0x85) & (self.__frame["data"][0] == subcmd_id))
		except IndexError:
			result = False
		return result

	def __extract_temp(self):
		fd = self.__frame["data"]

		# reshape string to be able to decode temps
		tempstr = fd[5:7]+fd[9:11]+fd[13:15]+fd[17:19]
		#self.temp = [(fd[6]<<8)+fd[5], (fd[10]<<8)+fd[9], (fd[14]<<8)+fd[13], (fd[18]<<8)+fd[17]]
		tmptemp = list(struct.unpack('<hhhh', tempstr))
		self.temp = map(lambda x: x/10, tmptemp)
		jsontemp = dict(zip(self.__temp_keys, self.temp))
		self.status.update(jsontemp)
		# print bypass here as the bypass state is transmitted far too oftern
		#log.info("Temps: %s, Bypass: %d, Replace filter in %d days" % (str(self.temp), self.bypass, self.filter_time_days))

	def __extract_bypass(self):
		self.bypass = self.__frame["data"][2] >> 4
		self.status['bypass'] = self.bypass

	def __extract_filter_time(self):
		self.filter_time_days = self.__frame["data"][25] | (self.__frame["data"][26] << 8)
		self.status['replace_filter'] = self.filter_time_days

	def __build_frame(self, cmd, data, adr=None, dataLen=None):
			if not adr:
				adr = self._addresses['MASTER']
			if not dataLen:
				dataLen = len(data)
			if cmd == self._known_commands['OTHER']:
					dataLen |= 0x80
			payload = adr + cmd.to_bytes(1,"little") + dataLen.to_bytes(1,"little")
			crc = self.__novus_crc(payload + data)
			return (payload + crc.to_bytes(2,"little") + data)

	def __broadcast_response(self, master_data):
		#device_descriptor = b'\x8f\x00P2HA000001A'
		device_descriptor = binascii.unhexlify("0d004554413030333645333042")
		data = master_data + device_descriptor
		self.__write(self.__build_frame(self._known_commands['BROADCAST_ANSWER'], data))

	def __ask_response(self):
		self.__write(self.__build_frame(self._known_commands['OTHER'], self.__ask_data))

	def __ping_response(self):
		self.__write(self.__build_frame(self._known_commands['GET_SET'], self.__ping_data))

	def __process_frame(self):
		# process frames addressed to me...
		# So far, answering on broadcast request stalls the bus as we don't know how to properly respond to ASK command
		# we still have to figure out what to send with ask response in order to send commands to the unit...
		if True: #self.__frame['dst'] == self._addresses['MY_ADDR']:
		# 	if self.__frame['cmd'] == self._known_commands['BROADCAST_REQUEST']:
		# 		log.info("Presence response requested.")
		# 		self.__broadcast_response(self.__frame['data'])
		# 	elif self.__frame['cmd'] == self._known_commands['BROADCAST_ANSWER']:
		# 		log.info("Presence accepted.")
		# 	elif self.__frame['cmd'] == self._known_commands['PING']:
		# 		log.info("Ping request.")
		# 		self.__ping_response()
		# 	elif self.__frame['cmd'] == self._known_commands['ASK']:
		# 		log.info("Ask request")
		# 		self.__ask_response()
		# else:
			# store ask response of other devices as we don't really know what is in there. When ask, we respond with
			# whatever other devices respond
			if (self.__frame['cmd'] == self._known_commands['OTHER']):
				self.__ask_data = self.__frame['data']
				# self.__ask_data = b'\x00' + bytes([self.__ask_data[1]+6, self.__ask_data[2] + 5])
			# process frames for monitored values
			if (self.__is_subcmd(self.subcmds['get_temps'])):
				self.__extract_temp()
			elif self.__is_subcmd(self.subcmds['get_bypass']):
				self.__extract_bypass()
			elif self.__is_subcmd(self.subcmds['get_filter_time_left']):
				if (self.__frame['size'] == 32):
					self.__extract_filter_time()


	def __decode_frame(self):
		header = struct.unpack('HBBH', self.__frame['raw'])
		dictkeys = ['dst', 'cmd', 'size', 'crc']
		self.__frame.update(dict(zip(dictkeys, header)))
		if (self.__validate_frame_command() == False):
			log.error("Invalid command: %s %s" % (binascii.hexlify(self.__frame['raw']), binascii.hexlify(self.__read(19))))
			# input("pause")
			return False
		# Overwrite dst with binary string... makes more sense than an integer
		self.__frame['dst'] = self.__frame['raw'][0:2]
		return True


	""" Decode and store a new frame """
	def receive_frame(self):
		dataoffset = 0
		# Find first command id
		r = 0
		# Read byte by byte until command start is detected
		r = self.__read(1)
		# raw has to be define as we want to output data together with previus data in case of error
		if (('raw' in self.__frame) == False):
			self.__frame['raw'] = b''
		invalid_data = b''
		address_invalid = True
		while (address_invalid):
			while (not (r in self._address_start_bytes)):		# read data until valid start address is detected
				r = self.__read(1)
				invalid_data += r
			address = r + self.__read(1)
			if address in self._addresses.values():
				address_invalid = False
			else:
				log.error("Invalid Address %s"% binascii.hexlify(address))
				invalid_data += address
		if (len(invalid_data)):									# there is some invalid data
			log.error("Data integrity error OK<ERR>OK %s<%s>%s" % (binascii.hexlify(self.__frame['raw']), binascii.hexlify(invalid_data), binascii.hexlify(address)))
			# input("pause")
		# start frame assembly
		self.__frame['raw'] = b''
		self.__frame['raw'] = address
		#read command, size and CRC
		r = self.__read(4)
		self.__frame['raw'] += r
		if not self.__decode_frame():
			return	# unable to decode, return
		# read data (len determined from size!)
		r = self.__read(self.__frame['size'] & 0x7F)		# bit 7 is used for something else :)
		self.__frame['raw'] += r
		self.__frame['data'] = r
		self.__validate_frame_crc()
		log.debug("dst:%s, cmd:%02x, size:%03d, data:%s" % (binascii.hexlify(self.__frame['dst']), self.__frame['cmd'], self.__frame['size'], binascii.hexlify(self.__frame['data'])))
		self.__process_frame()
		if (display_list):
			# out = self.log_unique(exclude_filter = [{"dst":0x0000}], include_filter = [{"cmd":0x85, "size": 3}])
			out = self.log_unique(exclude_filter=[{"dst": 0x0000}, {"cmd": 0x85, "size": 3},{"cmd": 0x85, "size": 32}, {"size": 0}, {"cmd": 0x85, "size": 19},{"cmd": 0x85, "size": 33}, {"cmd": 0x85, "size": 25}], include_filter=[])
			# out = self.log_unique(include_filter = [{"cmd":0x85}])
			#out = self.log_unique(include_filter=[{"dst": 0x0000}])
			try:
				if len(out):
					global text
					text.delete("0.0", tkinter.END)
					text.insert("0.0", out)
			except:
				print (out)

	""" Create a list of unique commands and return it in the form of a sorted string"""
	def log_unique(self, exclude_filter = [], include_filter = []):
		out = ""
		found = False
		try:
			# return if current frame matches exclude list
			for filter in exclude_filter:
				ex_keys = list(filter)
				ex_required = len(ex_keys)
				ex_found = 0
				for key in ex_keys:
					if filter[key] == self.__frame[key]:
						ex_found += 1
						# print("Filtered out!")
				if (ex_required == ex_found):
					return out
			# check if include filter is present
			if (len(include_filter)):
				#return if it does not match include filter
				incl_found = 0
				incl_required = 0
				incl_pass = False
				for filter in include_filter:
					incl_keys = list(filter)
					incl_required = len(incl_keys)
					incl_found = 0
					for key in incl_keys:
						if filter[key] == self.__frame[key]:
							incl_found += 1
					if (incl_found == incl_required):
						incl_pass = True
						break
				if (incl_pass == False):
					return out 				# frame not in include filter
			now = time.time() - self._start_time
			for f in self._frames_list:
				if (self.__frame['raw'] != f['raw']):
					continue
				found = True

				f['delta_t'] = now - f['ts']
				f['ts'] = now

			if (found == False):
				self.__frame['ts'] = now
				self.__frame['delta_t'] = 0.0
				self._frames_list.append(dict(self.__frame))		# dict creates a copy!!!
		except KeyError:
			self.__frame['ts'] = now
			self.__frame['delta_t'] = 0.0
			self._frames_list=[dict(self.__frame)]

		idx = 0
		out = ""
		sd = sorted(self._frames_list, key=lambda i: i['dst'])
		for f in sd:
			out += "%03d: dst:%s, cmd:%02x, size:%03d, ts:%010.3f, delta_t:%05.3f data:%s\n" % (
			idx, binascii.hexlify(f['dst']), f['cmd'], f['size'], f['ts'], f['delta_t'], binascii.hexlify(f['data']))
			idx += 1

		return out

def paul():
	#s = serial.Serial('/dev/ttyUSB0', 9600, timeout=0.06, parity=serial.PARITY_NONE, rtscts=1 )
	port = 'com10'
	baud = 9600
	ser = serial.Serial(port, baudrate=baud, timeout=20
						, stopbits=serial.STOPBITS_ONE,
						parity=serial.PARITY_MARK,
						bytesize=serial.EIGHTBITS
						# rtscts=False,
						# dsrdtr=False
						)
	ser.set_buffer_size(rx_size = 12000, tx_size = 12000)
	buffer = ""
	state = "unsync"
	p = Paul(ser)
	while True:
		p.receive_frame()


# def check_gui_update():
# 	global q
# 	global text
# 	data = q.get()
# 	text.delete("0.0", tkinter.END)
# 	text.insert("0.0", data)
# 	root.after(200, check_gui_update)
#

#x = threading.Thread(target=paul, args=())
#x.start()

if (display_list):
	root=tkinter.Tk()
	text = tkinter.Text(root, width = 200, height = 50)
	text.pack()
	#root.after(200, check_gui_update)
	root.mainloop()

	exit()

