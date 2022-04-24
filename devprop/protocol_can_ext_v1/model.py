from enum import Enum
from typing import NewType

ID_FIXED_MASK = 0x1FFE0000
ID_FIXED_PART = 0x1EF00000
MIN_PROPERTY_INDEX = 1
MAX_PROPERTY_INDEX = 255
MAX_NODE_ID = 32
SEGMENT_SIZE = 8


NodeId = NewType("NodeId", int)


class Opcode(Enum):
    READ_MANIFEST = 0
    READ_PROPERTY = 1
    WRITE_PROPERTY = 2
    ERROR = 7


class Direction(Enum):
    DEVICE_TO_CLIENT = 0
    CLIENT_TO_DEVICE = 1


class ErrorCode(Enum):
    GENERIC_ERROR = 1
    PROTOCOL_ERROR = 2
    NOT_IMPLEMENTED = 3
    INTERNAL_ERROR = 4


class ProtocolError(Exception):
    pass
