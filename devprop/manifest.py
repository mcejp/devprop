from dataclasses import dataclass
import hashlib
import logging
import struct
from typing import List, NewType, Optional, Sequence
import zlib

import yaml

from .model import Manifest, Property, PropertyType


ManifestEnvelope = NewType("ManifestEnvelope", bytes)


HEADER_LENGTH = 7
DRAFT_CSV_ZLIB = 0xF1


logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    message: str
    property_name: Optional[str]

    def __str__(self):
        return (f"property {self.property_name}: " if self.property_name is not None else "") + self.message


def check_envelope_header(envelope: bytes) -> int:
    """
    :param envelope: at least `_HEADER_LENGTH` initial bytes
    :return:
    """
    hash, length, version = struct.unpack("<4sHB", envelope[0:7])

    return HEADER_LENGTH + length


def add_envelope(manifest_payload: bytes, version: int) -> ManifestEnvelope:
    assert version == DRAFT_CSV_ZLIB

    # compress
    compressed = zlib.compress(manifest_payload, level=9)

    hash = hashlib.sha1(compressed)
    # print(hash)

    header = struct.pack("<4sHB", hash.digest()[0:4], len(compressed), DRAFT_CSV_ZLIB)

    return ManifestEnvelope(header + compressed)


def parse_enveloped_manifest(envelope: ManifestEnvelope) -> Manifest:
    hash, length, version = struct.unpack("<4sHB", envelope[0:7])
    logger.debug("Manifest header HASH=%sh LEN=%d VERSION=%d", hash.hex(), length, version)

    compressed_data = envelope[7:]
    assert len(compressed_data) == length

    if version == DRAFT_CSV_ZLIB:
        hash_computed = hashlib.sha1(compressed_data)
        assert hash_computed.digest()[0:4] == hash
        manifest_bytes = zlib.decompress(compressed_data)
        return parse_manifest_draft_csv(manifest_bytes)
    else:
        raise Exception(f"Unknown manifest version 0x{version:02X}")


def parse_manifest_draft_csv(encoded: bytes) -> Manifest:
    decoded = encoded.decode()

    lines = decoded.split("\n")
    device_name = lines[0]
    properties: List[Property] = []

    for line in lines[1:]:
        if not line:
            continue

        index = 1 + len(properties)
        name, type_code, unit, offset_str, scale_str, min_str, max_str, operations_str = line.split(",")
        properties.append(Property(index, name, PropertyType(type_code), unit, offset_str, scale_str, (min_str, max_str), operations_str))

    return Manifest(device_name, properties)


def parse_manifest_yaml(input) -> Manifest:
    device_model = yaml.safe_load(input)

    device_name = device_model["device_name"]
    properties: List[Property] = []

    for property_model in device_model["properties"]:
        index = 1 + len(properties)

        name = property_model["name"]
        assert isinstance(name, str)

        type_attributes = property_model["type"]
        assert isinstance(type_attributes, str)

        operations_str = None
        type = None
        for at in type_attributes.split(" "):
            if at == "readonly":
                assert operations_str is None
                operations_str = "r"
            elif at == "writeonly":
                assert operations_str is None
                operations_str = "w"
            else:
                type = PropertyType[at.upper()]

        if operations_str is None:
            operations_str = "rw"
        assert type is not None

        unit = property_model.get("unit", "")
        assert isinstance(unit, str)
        offset = property_model.get("offset", 0)
        assert isinstance(offset, (int, float)) and not isinstance(offset, bool)
        scale = property_model.get("scale", 1)
        assert isinstance(scale, (int, float)) and not isinstance(scale, bool)
        assert scale != 0
        if "range" in property_model:
            range = property_model["range"]
            assert isinstance(range, list)
        else:
            # default to natural range of data type
            range = type.range_inclusive

        min_, max_ = range
        assert isinstance(min_, (int, float)) and not isinstance(min_, bool)
        assert isinstance(max_, (int, float)) and not isinstance(max_, bool)

        # https://stackoverflow.com/a/63944491
        def without_keys(d, keys):
            return {k: d[k] for k in d.keys() - keys}

        additional_attributes = without_keys(property_model, {"name", "type", "unit", "offset", "scale", "range"})

        properties.append(Property(index, name, type, unit, str(offset), str(scale), (str(min_), str(max_)), operations_str,
                                   additional_attributes=additional_attributes))

    return Manifest(device_name, properties)


def serialize_manifest_draft_csv(manifest: Manifest) -> bytes:
    s = manifest.device_name + "\n"

    for p in manifest.properties:
        s += f"{p.name},{p.type.value},{p.unit},{p.offset_str},{p.scale_str},{p.range_str[0]},{p.range_str[1]},{p.operations_str}\n"

    return s.encode()


def validate_manifest(manifest: Manifest) -> Sequence[ValidationError]:
    # TODO: validate all names
    # TODO: validate property names unique

    errors = []

    def error(*args, **kwargs):
        errors.append(ValidationError(*args, **kwargs))

    for property in manifest.properties:
        def test_numeric(str_value, attribute_desc) -> Optional[float]:
            try:
                return float(str_value)
            except:
                error(f"{attribute_desc} '{str_value}' not a valid numeric value", property_name=property.name)
                return None

        offset = test_numeric(property.offset_str, "offset")
        scale = test_numeric(property.scale_str, "scale")
        min_ = test_numeric(property.range_str[0], "minimum")
        max_ = test_numeric(property.range_str[1], "maximum")

        if scale is not None and abs(scale) < 1e-5:
            error(f"scale must not be zero", property_name=property.name)

        if offset is not None and scale is not None:
            min_value = offset + property.type.range_inclusive[0] * scale
            max_value = offset + property.type.range_inclusive[1] * scale

            if min_ is not None and min_ < min_value:
                error(f"specified minimum {min_:.3g} outside of expressable range [{min_value:.3g}; {max_value:.3g}]", property_name=property.name)

            if max_ is not None and max_ > max_value:
                error(f"specified maximum {min_:.3g} outside of expressable range [{min_value:.3g}; {max_value:.3g}]", property_name=property.name)

        if min_ is not None and max_ is not None and min_ >= max_:
            error(f"maximum must be larger than minimum", property_name=property.name)

    return errors
