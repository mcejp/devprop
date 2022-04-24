from typing import Tuple

from devprop.can_bus.adapter import Message
from .model import (
    Direction,
    ErrorCode,
    ID_FIXED_MASK,
    ID_FIXED_PART,
    MAX_PROPERTY_INDEX,
    MIN_PROPERTY_INDEX,
    NodeId,
    Opcode,
)


def make_error_response(node_id: int, property_index: int, opcode: Opcode, error_code: ErrorCode) -> Message:
    return Message(
        id=make_frame_id(node_id, property_index, Opcode.ERROR, Direction.DEVICE_TO_CLIENT),
        data=bytes([opcode.value, error_code.value]),
    )


def make_frame_id(node_id: int, property_index: int, opcode: Opcode, dir: Direction) -> int:
    if opcode in {Opcode.READ_PROPERTY, Opcode.WRITE_PROPERTY}:
        assert property_index >= MIN_PROPERTY_INDEX
        assert property_index <= MAX_PROPERTY_INDEX
    else:
        assert property_index >= 0
        assert property_index < 0x100

    assert node_id >= 0
    assert node_id < 32

    return ID_FIXED_PART | (dir.value << 16) | (node_id << 11) | (opcode.value << 8) | property_index


def make_read_manifest_request(node_id: int, segment: int) -> Message:
    return Message(
        id=make_frame_id(node_id, segment, Opcode.READ_MANIFEST, Direction.CLIENT_TO_DEVICE),
        data=b"",
    )


def make_read_manifest_response(node_id: int, segment: int, payload: bytes) -> Message:
    return Message(
        id=make_frame_id(node_id, segment, Opcode.READ_MANIFEST, Direction.DEVICE_TO_CLIENT),
        data=payload,
    )


def make_read_property_request(node_id: int, property_index: int) -> Message:
    return Message(
        id=make_frame_id(node_id, property_index, Opcode.READ_PROPERTY, Direction.CLIENT_TO_DEVICE),
        data=b"",
    )


def make_read_property_response(node_id: int, property_index: int, payload: bytes) -> Message:
    return Message(
        id=make_frame_id(node_id, property_index, Opcode.READ_PROPERTY, Direction.DEVICE_TO_CLIENT),
        data=payload,
    )


def make_write_property_request(node_id: int, property_index: int, payload: bytes) -> Message:
    return Message(
        id=make_frame_id(node_id, property_index, Opcode.WRITE_PROPERTY, Direction.CLIENT_TO_DEVICE),
        data=payload,
    )


def make_write_property_response(node_id: int, property_index: int, payload: bytes) -> Message:
    return Message(
        id=make_frame_id(node_id, property_index, Opcode.WRITE_PROPERTY, Direction.DEVICE_TO_CLIENT),
        data=payload,
    )


def stringify(msg: Message) -> str:
    node_id, property_index, opcode, dir = unpack_id(msg.id)

    if opcode is Opcode.ERROR and dir is Direction.DEVICE_TO_CLIENT and len(msg.data) == 2:
        try:
            request_opcode_name = Opcode(msg.data[0]).name
        except ValueError:
            request_opcode_name = f"{msg.data[0]:02X}"

        try:
            error_code_name = ErrorCode(msg.data[1]).name
        except ValueError:
            error_code_name = f"{msg.data[1]:02X}"

        return f"NODE_ID={node_id} ERROR=(INDEX={property_index} OPCODE={msg.data[0]:X}-{request_opcode_name}) ERROR_CODE={error_code_name}"
    else:
        payload_str = f" PAYLOAD={msg.data.hex('_')}"

        return (
            f"NODE_ID={node_id} INDEX={property_index} OPCODE={opcode.value:X}-{opcode.name} DIR={dir.name}"
            + payload_str
        )


def unpack_id(id: int) -> Tuple[NodeId, int, Opcode, Direction]:
    """
    :param id:
    :return: (node_id, property_index, opcode, direction)
    """
    assert (id & ID_FIXED_MASK) == ID_FIXED_PART

    property_index = id & 0xFF
    opcode_int = (id >> 8) & 7
    node_id = (id >> 11) & 31
    dir_int = (id >> 16) & 1

    return NodeId(node_id), property_index, Opcode(opcode_int), Direction(dir_int)
