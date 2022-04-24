import logging
from typing import Any

from .model import Property, PropertyType


logger = logging.getLogger(__name__)


def decode_value(property: Property, value: bytes) -> float:
    if property.type is PropertyType.UINT8:
        assert len(value) == 1
        raw_value = int.from_bytes(value, byteorder="little", signed=False)
    elif property.type is PropertyType.UINT16:
        assert len(value) == 2
        raw_value = int.from_bytes(value, byteorder="little", signed=False)
    elif property.type is PropertyType.UINT32:
        assert len(value) == 4
        raw_value = int.from_bytes(value, byteorder="little", signed=False)
    else:
        raise NotImplementedError()

    physical_value = float(property.offset_str) + raw_value * float(property.scale_str)

    if physical_value < float(property.range_str[0]) or physical_value > float(property.range_str[1]):
        logger.warning("Property %s value %f out of allowed range (%s; %s)", property.name, physical_value, property.range_str[0], property.range_str[1])

    return physical_value


def encode_value(property: Property, physical_value: float) -> bytes:
    if physical_value < float(property.range_str[0]) or physical_value > float(property.range_str[1]):
        raise Exception("Property %s value %f out of allowed range (%s; %s)" % (property.name, physical_value, property.range_str[0], property.range_str[1]))

    raw_value = (physical_value - float(property.offset_str)) / float(property.scale_str)

    if property.type is PropertyType.UINT8:
        return int(round(raw_value)).to_bytes(1, byteorder="little", signed=False)
    elif property.type is PropertyType.UINT16:
        return int(round(raw_value)).to_bytes(2, byteorder="little", signed=False)
    elif property.type is PropertyType.UINT32:
        return int(round(raw_value)).to_bytes(4, byteorder="little", signed=False)
    else:
        raise NotImplementedError()
