import time
import logging
import struct
from typing import Optional

from cobs import cobs
import serial

from .adapter import BusAdapter, Message
from ..protocol_can_ext_v1.messages import stringify


logger = logging.getLogger(__name__)


# found online and adapted
def crc16_kermit(data):
    crc = 0

    for i in range(len(data)):
        crc ^= data[i]
        for j in range(0,8):
            if (crc & 1) > 0:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc = crc >> 1

    return crc


class SerialWrappedCanAdapter(BusAdapter):
    def __init__(self, port: str):
        self._port = serial.Serial(port, 115200)
        self._buffer = bytearray()

    def receive(self, deadline: Optional[float] = None) -> Message:
        while True:
            if deadline is not None:
                timeout = deadline - time.monotonic()

                if timeout < 0:
                    raise TimeoutError()
            else:
                timeout = None

            self._port.timeout = timeout
            # problem: if we allow reception of multiple bytes, we end up stalling here
            #          and we run out of time to load the following segments of the manifest
            input = self._port.read(1)

            if input is None:
                raise TimeoutError()

            self._buffer += input

            # loop until valid frame decoded, or run out of terminators
            while True:
                # attempt to parse input
                terminator_pos = self._buffer.find(b"\x00")

                if terminator_pos < 0:
                    break

                encoded = self._buffer[0:terminator_pos]
                self._buffer = self._buffer[terminator_pos + 1:]

                if len(encoded) == 0:
                    # print("empty")
                    continue

                try:
                    frame = cobs.decode(encoded)
                except cobs.DecodeError:
                    # print("bad frame", encoded.hex())
                    continue

                crc, = struct.unpack("<H", frame[-2:])
                
                if crc != crc16_kermit(frame[:-2]):
                    # print("bad CRC", frame.hex())
                    continue

                id, = struct.unpack("<I", frame[:4])
                msg = Message(id=id, data=frame[4:-2])

                logger.debug("Rx frame %08xh [%-23s] %s", msg.id, msg.data.hex(" "), stringify(msg))

                return msg

    def send(self, msg: Message):
        logger.debug("Tx frame %08xh [%-23s] %s", msg.id, msg.data.hex(" "), stringify(msg))

        header = struct.pack("<I", msg.id)
        crc = crc16_kermit(header + msg.data)
        frame = cobs.encode(header + msg.data + struct.pack("<H", crc))
        # print((header + msg.data + struct.pack("<H", crc)).hex())
        # print(frame.hex())
        self._port.write(b"\x00" + frame + b"\x00")
