from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple


class PropertyType(Enum):
    INT8 = "b"
    INT16 = "h"
    INT32 = "i"
    UINT8 = "B"
    UINT16 = "H"
    UINT32 = "I"

    @property
    def range_inclusive(self):
        range_by_type = {
            PropertyType.INT8: (-2**7, 2**7-1),
            PropertyType.INT16: (-2**15, 2**15-1),
            PropertyType.INT32: (-2**31, 2**31-1),
            PropertyType.UINT8: (0, 2**8-1),
            PropertyType.UINT16: (0, 2**16-1),
            PropertyType.UINT32: (0, 2**32-1),
        }
        return range_by_type[self]


@dataclass
class Property:
    index: int
    name: str
    type: PropertyType
    unit: str
    offset_str: str
    scale_str: str
    range_str: Tuple[str, str]
    operations_str: str

    additional_attributes: Dict[str, Any] = None

    @property
    def readable(self):
        return "r" in self.operations_str

    @property
    def writable(self):
        return "w" in self.operations_str

@dataclass
class Manifest:
    device_name: str
    properties: List[Property]
