#!/usr/bin/env python3
"""
Main (reference) ocarina API, the only one officially supported!
"""

API_VERSION = 2

import serial, struct
from time import sleep
from enum import IntEnum, Enum
import threading
import logging
import sys
from typing import Optional, Type, TypeVar
import queue

class CMD(Enum):
	AUTO_BITRATE =          b'a'
	SET_BITRATE =           b'b'
	QUERY_COUNTERS =        b'c'
	RESET_COUNTERS =        b'C'
	DFU =                   b'd'#//reboot to DFU BL
	QUERY_ERROR_FLAGS =     b'e'
	RX_FORWARDING_ENABLE =  b'F'
	RX_FORWARDING_DISABLE = b'f'
	QUERY_CONFIG =          b'g'
	QUERY_INTERFACE_ID =    b'i'
	SEND_MESSAGE_STD_ID =   b'm'
	SEND_MESSAGE_EXT_ID =   b'M'
	NOP =                   b'n'
	LOOPBACK_ENABLE =       b'L'
	LOOPBACK_DISABLE =      b'l'
	RESET =                 b'r'#//writes 24x 0xAA, host expects, there can't be same regular response
	SILENT_ENABLE =         b'S'
	SILENT_DISABLE =        b's'
	QUERY_VERSION =         b'v'
	
class DTH(Enum):
	INTERFACE_ID =      CMD.QUERY_INTERFACE_ID.value
	ERROR_FLAGS =       CMD.QUERY_ERROR_FLAGS.value
	ERROR_ON_CAN =      b'E'
	MESSAGE_STD_ID =    CMD.SEND_MESSAGE_STD_ID.value
	MESSAGE_EXT_ID =    CMD.SEND_MESSAGE_EXT_ID.value
	CONFIG =            CMD.QUERY_CONFIG.value
	VERSION =           CMD.QUERY_VERSION.value
	COUNTERS =          CMD.QUERY_COUNTERS.value
	HEARTBEAT =         b'h'

	@classmethod
	def has_value(cls, value : int) -> bool:
		return value in cls._value2member_map_

class PROTOCOL:
	VERSION = 3

B = TypeVar('T', bound='BITRATE')

class BITRATE(Enum):
	UNKNOWN =   (0, None)
	KBIT10 =    (1, 10)
	MIN =       KBIT10
	KBIT20 =    (2, 20)
	KBIT50 =    (3, 50)
	KBIT100 =   (4, 100)
	KBIT125 =   (5, 125)
	KBIT250 =   (6, 250)
	KBIT500 =   (7, 500)
	KBIT800 =   (8, 800)
	KBIT1000 =  (9, 1000)
	MAX   =     KBIT1000

	@classmethod
	def fromIdentifier(cls, value : int) -> B:
		for e in cls:
			if e.value[0] == value:
				return e
		return cls.UNKNOWN
	
	@classmethod
	def fromKbit(cls, value : int) -> B:
		for e in cls:
			if e.value[1] == value:
				return e
		return cls.UNKNOWN

class ERRORFLAG(IntEnum):
	USBIN_OVERFLOW          = 0
	USBOUT_OVERFLOW         = 1
	CANIN_OVERFLOW          = 2
	CANOUT_OVERFLOW         = 3
	INVALID_CAN_MSG_REQUEST = 4
	INVALID_COMMAND         = 5
	NOT_INITIALIZED_TX      = 6
	INVALID_TLV             = 7
	TOO_LONG_TLV            = 8

class CANERROR(IntEnum):
	#0~7 direct mapping of LEC
	NONE =            0
	STUFF =           1
	FORM =            2
	ACKNOWLEDGMENT =  3
	BIT_RECESSIVE =   4
	BIT_DOMINANT =    5
	CRC =             6
	SET_BY_SW =       7

	UNKNOWN =        15

class CANBUSSTATE:
	OK =      0
	PASSIVE = 1
	OFF =     2

	def __init__(self, value) -> None:
		self.value = value
	
	def __str__(self) -> str:
		if self.value == self.OK:
			return "OK"
		if self.value == self.PASSIVE:
			return "PASSIVE"
		if self.value == self.OFF:
			return "OFF"
		else:
			return "NOT SUPPORTED"
		


SYNC_FRAME = [0xAA] * 24

class IDTYPE(IntEnum):
	STD = 0
	EXT = 1

#data classes
class CanMsgID:
	def __init__(self, value, idType) -> None:
		self.value = value
		if idType not in [IDTYPE.STD, IDTYPE.EXT]:
			raise TypeError("Bad ID type")
		self.type = idType


#event classes
class Event:
	pass

class HeartbeatEvent(Event):
	def __str__(self) -> str:
		return "Heartbeat Event"

class VersionEvent(Event):
	protocol : int
	sw : int
	hw : int
	hwRevision : int

	def __init__(self, protocol : int, sw : int, hw : int, hwRevision : int) -> None:
		self.protocol = protocol
		self.sw = sw
		self.hw = hw
		self.hwRevision = hwRevision
	
	def __str__(self) -> str:
		return f'VersionEvent(Protocol {self.protocol:2d} | SW {self.sw:2d} | HW {self.hw:2d} | HWrev {self.hwRevision:2d}'


class CanMsgEvent(Event):
	id : CanMsgID
	data : bytes
	timestamp : int 

	def __init__(self, id : CanMsgID, data : bytes, timestamp : int) -> None:
		self.id = id
		self.data = data
		self.timestamp = timestamp

	def __str__(self) -> str:
		return f"CanMsgEvent({'STD' if self.id.type == IDTYPE.STD else 'EXT'} @ {self.timestamp/1e6:13.6f} ID: {self.id.value:8X} data({len(self.data):2d}): {' '.join([f'{b:02X}' for b in self.data])})"

class CANErrorEvent(Event):
	TEC : int
	REC : int
	busState : CANBUSSTATE
	eType : CANERROR
	timestamp : int

	def __init__(self, TEC : int, REC : int, busState : CANBUSSTATE, eType : CANERROR, timestamp : int) -> None:
		self.TEC = TEC
		self.REC = REC
		self.busState = busState
		self.eType = eType
		self.timestamp = timestamp

	def __str__(self) -> str:
		return f'CanErrorEvent(ERR @ {self.timestamp/1e6:4.6f} error: {self.eType} busState: {self.busState}, TEC: {self.TEC:3d}, REC: {self.REC:3d})'

class ErrorFlagsEvent(Event):
	values : int
	flags : list[ERRORFLAG]


	def __init__(self, value : int) -> None:
		self.value = value

		self.flags = []
		if value:
			for f in ERRORFLAG:
				if value & (1 << f.value):
					self.flags.append(f)

	def __str__(self) -> str:
		buffer = f'ErrorFlagsEvent(0x{self.value:04X})'
		value = self.value
		if self.flags:
			buffer += " ["
			for f in self.flags:
				buffer += f"{f.name}, "
				value ^= 1 << f.value  # clear this bit, to know if there were some unknown bits set
			buffer = f"{buffer[:-2]}]"
		if value:
			buffer += f" + undocumeneted {value:04X}"
		return buffer
			

class IfaceIdEvent(Event):
	if_id : str

	def __init__(self, if_id) -> None:
		self.if_id = if_id

	def __str__(self) -> str:
		return 'IfaceIdEvent({:s})'.format(self.if_id)

class ConfigEvent(Event):
	bitrate : BITRATE
	silent : bool
	loopback : bool
	forward : bool

	def __init__(self, bitrate : BITRATE, silent : bool, loopback : bool, forward : bool) -> None:
		self.bitrate = bitrate
		self.silent = silent
		self.loopback = loopback
		self.forward = forward

	def __str__(self) -> str:
		return f"ConfigEvent( enum {self.bitrate} = {self.bitrate.value[1]} kbit/s, silent({'X' if self.silent else ' '}) | loopback({'X' if self.loopback else ' '}) | forward({'X' if self.forward else ' '}))"

# class ProtocolEvent(Event):
# 	def __init__(self, protocol) -> None:
# 		self.version = int(protocol)

# 	def __str__(self) -> str:
# 		return f'ProtocolEvent({self.version:d})'

class CountersEvent(Event):
	rxed : int
	txed : int

	def __init__(self, rxed : int, txed : int) -> None:
		self.rxed = rxed
		self.txed = txed

	def __str__(self) -> str:
		return f'CountersEvent(RX: {self.rxed:6d}, TX: {self.txed:6d})'

class Payload:
	def __init__(self, data : bytes) -> None:
		if not isinstance(data, bytes):
			raise TypeError("payload must be in bytes")
		self.data = data
	
	def pop(self, amount : Optional[int] = None) -> bytes:
		if amount == None:
			requested = self.data
			self.data = []
		else:
			requested, self.data = self.data[0:amount], self.data[amount:]
		return requested
	
	def popu8(self) -> int:
		return struct.unpack('B', self.pop(1))[0]
	
	def popu16(self) -> int:
		return struct.unpack('H', self.pop(2))[0]
	
	def popu32(self) -> int:
		return struct.unpack('I', self.pop(4))[0]
	
	def isEmpty(self) -> bool:
		return len(self.data) == 0
	
	def length(self) -> int:
		return len(self.data)
	
	def __str__(self) -> str:
		return str(self.data)

class Ocarina:
	log : logging.Logger
	ser : serial.Serial
	eventListener : threading.Thread
	eventQueue : queue.Queue

	def __init__(self, port : str, maxRxQueueSize : Optional[int] = None, logger : logging.Logger = None) -> None:
		"""
		Ocarina API class

		:param port: identifier of com port ('/dev/ttyACM0', '/dev/ocarina', 'COM1', ....)
		:type port: str
		:param maxRxQueueSize: maximum rx event queue size, defaults to None (unlimited)
		:type maxRxQueueSize: Optional[int], optional
		:param logger: parent logger instance to get child logger from, defaults to None (gets child logger from root logger)
		:type logger: logging.Logger, optional
		"""
		self.log = (logger if logger else logging.getLogger()).getChild("OCA")
		self.ser = None # because when next line fails, self.ser would not exist and we would have troubles in destructor
		self.ser = serial.Serial(port, 115200, timeout= 2.0) # HeartBeat comes each second, so timeout should never happen, baudrate is not important for VCOM
		self.log.debug(f"device {port} opened")

		# flush RX buffers
		self.nop()#hack to trigger potential input buffer autoflush when there is some garbage
		self._connect()
		self.eventQueue = queue.Queue()
		self.eventListener = threading.Thread(target=self._event_listener, daemon=True)
		self.eventListener.start()

	def __del__(self) -> None:
		self.log.debug("destroying ocarina session")
		if self.ser != None:
			self.log.debug("auto disabling message forwarding")
			self.set_message_forwarding(False)
			self.log.debug("closing")
			self.ser.close()
	
	def __enter__(self) -> None:
		return self
	
	def __exit__(self ,type, value, traceback):
		pass

	def _close(self) -> None:
		self.ser.close()
	
	def _write(self, data : bytes) -> int:
		return self.ser.write(data)
	
	def _read(self, length : int) -> bytes:
		return self.ser.read(length)

	def _connect(self):
		"""
		Initializes device by resetting CAN iface config and synchronizing HOST-DEVICE communications
		"""
		self.log.debug("initializing connection to ocarina")
		self._write_command(CMD.RESET)
		sync_reply = []
		cnt = 0
		while(sync_reply != SYNC_FRAME):
			cnt += 1
			sync_reply.append(ord(self._read(1)))
			if len(sync_reply) > len(SYNC_FRAME):
				sync_reply = sync_reply[-len(SYNC_FRAME):]#match length to extecped SYNC_FRAME length by leaving last N elements
		self.log.debug(f"Initialized, skipped bytes: {cnt-len(SYNC_FRAME):d}")
	
	def _write_command(self, command : CMD, data : bytes= bytes()) -> None:
		"""
		Internal, writes command into Ocarina.

		:param command: Command to send
		:type command: CMD
		:param data: payload of command, defaults to bytes()
		:type data: bytes, optional
		"""
		written = self._write(command.value+bytes([len(data)])+data)
		assert(written == 2+len(data))
	
	def _event_listener(self):
		"""
		Internal function extracting event from data and putting them into eventQueue. Runs in separate thread.
		"""
		elog = self.log.getChild("EVTRX")
		elog.info("event listener started")

		# TODO: decide, how to handle queue overflow, right now, overflow is not even caught and is propagater further
		while(True):
			frameType = self._read(1)
			if len(frameType)==0:
				elog.warning("communication timeouted, at least heartbeats should come...")
				continue

			frameLength = struct.unpack('B', self._read(1))[0]
			payload = Payload(self._read(frameLength))

			if DTH.has_value(frameType):
				frameType = DTH(frameType)
				elog.debug(f"got event {frameType} with payload length {payload.length()} bytes")
			else:
				elog.warning(f"unknown event. {frameType} with payload length {payload.length()} bytes, protocol changed?")
				continue

			if frameType == DTH.INTERFACE_ID:
				self.eventQueue.put_nowait(IfaceIdEvent(payload.pop().decode()))

			elif frameType == DTH.MESSAGE_STD_ID:
				ts = payload.popu8() + (payload.popu32()<<8)#in us
				sid = CanMsgID(payload.popu16(), IDTYPE.STD)
				data = payload.pop()
				self.eventQueue.put_nowait(CanMsgEvent(sid, data, ts))

			elif frameType == DTH.MESSAGE_EXT_ID:
				ts = payload.popu8() + (payload.popu32()<<8)#in us
				eid = CanMsgID(payload.popu32(), IDTYPE.EXT)
				data = payload.pop()
				self.eventQueue.put_nowait(CanMsgEvent(eid, data, ts))
			
			elif frameType == DTH.ERROR_ON_CAN:
				ts = payload.popu8() + (payload.popu32()<<8)#in us
				TEC = payload.popu8()
				REC = payload.popu8()
				mixed = payload.popu8()
				state = CANBUSSTATE(mixed&0xF)
				eType = CANERROR(mixed>>4).name
				self.eventQueue.put_nowait(CANErrorEvent(TEC, REC, state, eType, ts))

			elif frameType == DTH.ERROR_FLAGS:
				value = payload.popu32()
				self.eventQueue.put_nowait(ErrorFlagsEvent(value))
			
			elif frameType == DTH.COUNTERS:
				rxed = payload.popu32()
				txed = payload.popu32()
				self.eventQueue.put_nowait(CountersEvent(rxed, txed))

			elif frameType == DTH.HEARTBEAT:
				HeartbeatEvent()
			
			elif frameType == DTH.CONFIG:
				raw = payload.popu8()
				self.eventQueue.put_nowait(ConfigEvent(bitrate = BITRATE.fromIdentifier(raw & 0xF), silent = bool(raw & (1<<4)), loopback = bool(raw & (1<<5)), forward = bool(raw & (1<<6))))
			
			elif frameType == DTH.VERSION:
				protocol = payload.popu8()
				sw = payload.popu8()
				hw = payload.popu8()
				hwRevision = payload.popu8()
				self.eventQueue.put_nowait(VersionEvent(protocol, sw, hw, hwRevision))

			else:
				elog.warning(f"unhandled event. {frameType} with payload length {payload.len()} bytes")
			
			if not payload.isEmpty():
				elog.warning(f"payload of event {frameType} was not fully consumed, protocol changed?") #some part of response was not read
			

	def read_event(self, timeout : Optional[float] = None) -> Event:
		"""
		Reads buffered events from Ocarina.

		:raises queue.Empty: when no event is available and timeout runs out
		:param timeout: timeout value, defaults to None, which blocks until next event arrives
		:type timeout: Optional[float], optional
		:return: event from Ocarina
		:rtype: Event
		"""
		if timeout == 0:
			return self.eventQueue.get_nowait()
		else:
			return self.eventQueue.get(block = True, timeout = timeout)

	def set_message_forwarding(self, enable : bool):
		"""
		Configures, if received messages are forwarded to host
		
		:param enable: requested state of forwarding
		:type enable: bool
		"""
		if enable:
			self._write_command(CMD.RX_FORWARDING_ENABLE)
		else:
			self._write_command(CMD.RX_FORWARDING_DISABLE)
	
	def set_loopback(self, enable : bool):
		"""
		Configures, if transmitted messages are also received (looped back)
		
		:param enable: requested state of loopback mode
		:type enable: bool
		"""
		if enable:
			self._write_command(CMD.LOOPBACK_ENABLE)
		else:
			self._write_command(CMD.LOOPBACK_DISABLE)
	
	def set_silent(self, enable : bool):
		"""
		Configures, if device may touch CAN bus at all
		
		:param enable: requested state of silent mode
		:type enable: bool
		"""
		if enable:
			self._write_command(CMD.SILENT_ENABLE)
		else:
			self._write_command(CMD.SILENT_DISABLE)


	def send_message_std(self, sid : int, data = []):
		"""
		Send STD ID message to CAN bus
		
		:param sid: STD ID of message
		:type sid: integer 11 bit
		:param data: message data, defaults to []
		:type data: list of integers <0;255>, optional
		:raises TypeError: if sid is not integer
		:raises ValueError: if sid >= 2^11
		:raises ValueError: if len(data) > 8
		"""
		if not isinstance(sid, int):
			raise TypeError("sid must have integer type")
		if sid >= 2**11:
			raise ValueError("sid must be in range <{0:4d}[{0:3X}];{1:4d}[{1:3X}]>",format(0, 2**11-1))
		if len(data) > 8:
			raise ValueError("data too long")
		self._write_command(CMD.SEND_MESSAGE_STD_ID, \
		struct.pack('H', sid) + bytes(data))

	def send_message_ext(self, eid : int, data = []):
		"""
		Send EXT ID message to CAN bus
		
		:param eid: EXT ID of message
		:type eid: integer 29 bit
		:param data: message data, defaults to []
		:type data: list of integers <0;255>, optional
		:raises TypeError: if eid is not integer
		:raises ValueError: if eid >= 2^29
		:raises ValueError: if len(data) > 8
		"""
		if not isinstance(eid, int):
			raise TypeError("eid must have integer type")
		if eid >= 2**29:
			raise ValueError("eid must be in range <{0:4d}[{0:3X}];{1:4d}[{1:3X}]>",format(0, 2**29-1))
		if len(data) > 8:
			raise ValueError("data too long")
		self._write_command(CMD.SEND_MESSAGE_EXT_ID, \
		struct.pack('I', eid) + bytes(data))

	def query_error_flags(self):
		"""
		query error flags from device and clear them
		"""
		self._write_command(CMD.QUERY_ERROR_FLAGS)
	
	def query_config(self):
		"""
		query current config from device (bitrate, silent, loopback, forwarding)
		"""
		self._write_command(CMD.QUERY_CONFIG)

	def query_interface(self):
		"""
		query device identification string
		"""
		self._write_command(CMD.QUERY_INTERFACE_ID)
	
	def query_version(self):
		"""
		query device versions (protocol, SW, HW, HW rev.)
		"""
		self._write_command(CMD.QUERY_VERSION)

	def query_counters(self):
		"""
		query device counters
		"""
		self._write_command(CMD.QUERY_COUNTERS)
	
	def reset_counters(self):
		"""
		reset device counters
		"""
		self._write_command(CMD.RESET_COUNTERS)
	
	def set_bitrate_manual(self, bitrate : BITRATE):
		"""
		set bitrate manually
		
		:param bitrate: requested bitrate
		:type bitrate: instance of Bitrate class
		"""
		self._write_command(CMD.SET_BITRATE, bytes([bitrate.value[0]]))
	
	def set_bitrate_auto(self):
		"""
		switch to auto bitrate mode
		"""
		self._write_command(CMD.AUTO_BITRATE)

	def reboot_to_DFU(self):
		"""
		reboot to bootloader, useful for flashing new version
		"""
		self._write_command(CMD.DFU)
	
	def nop(self):
		"""
		no operation command, useful to trigger ocarina input buffer autoflush when there is some garbage
		"""
		self._write_command(CMD.NOP)
	
	@staticmethod
	def getAPIversion():
		return API_VERSION
