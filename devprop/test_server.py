#!/usr/bin/env python3

import argparse
import logging
import struct
import traceback
from pathlib import Path
import random

from devprop.can_bus.adapter import Message
from devprop.manifest import DRAFT_CSV_ZLIB, add_envelope, parse_manifest_yaml, serialize_manifest_draft_csv
from devprop.protocol_can_ext_v1.messages import unpack_id, Direction, ErrorCode, make_error_response, \
    make_read_manifest_response, \
    make_read_property_response, Opcode, make_write_property_response

from devprop.can_bus.python_can_adapter import PythonCanAdapter

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig()
    logging.getLogger("devprop").setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("node_id", type=int)
    args = parser.parse_args()

    # MAX_FRAME_LEN = 100

    # if args.port.startswith("can:"):
    # import can_socket

    # sock = can_socket.CanSocket()
    # can_id = int(args.port[4:], base=0)
    bus = PythonCanAdapter()
    # bus.set_filters([dict(can_id=can_id, can_mask=0x7ff, extended=False)])
    logger.info("Listening on CAN bus")
    # else:
    #     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     server_address = "127.0.0.1"
    #     server = (server_address, int(args.port, base=0))
    #     sock.bind(server)
    #
    #     logger.info("Listening on " + server_address + ":" + str(args.port))

    if args.manifest.suffix.lower() in {".yml", ".yaml"}:
        # YAML manifest
        with open(args.manifest, "rt") as f:
            manifest = parse_manifest_yaml(f)

        manifest_payload = add_envelope(serialize_manifest_draft_csv(manifest), DRAFT_CSV_ZLIB)
    else:
        # assume binary
        manifest_payload = args.manifest.read_bytes()

    property_values = {}

    while True:
        # (client_address, client_port)
        msg = bus.receive()
        node_id, property_index, opcode, direction = unpack_id(msg.id)

        if node_id != args.node_id:
            continue

        assert direction is Direction.CLIENT_TO_DEVICE

        resp: Message

        try:
            if opcode is Opcode.READ_MANIFEST:
                segment = property_index
                # byte_offset = p.unpack_get_manifest_request(payload)
                # reply = p.make_get_manifest_response(tx_id, file_contents[byte_offset:byte_offset + 7])
                resp = make_read_manifest_response(node_id, segment, manifest_payload[segment * 8:(segment + 1) * 8])
            elif opcode == Opcode.READ_PROPERTY:
                try:
                    value = property_values[property_index]
                except KeyError:
                    value = random.randint(0, 2**16 - 1)
                    property_values[property_index] = value
                # reply = p.pack_frame(p.Opcode.GET_PROPERTY, tx_id, bytes([value & 0xff, value >> 8]))
                resp = make_read_property_response(node_id, property_index, bytes([value & 0xff, value >> 8]))
            elif opcode == Opcode.WRITE_PROPERTY:
                # resp = make_error_response(node_id, property_index, opcode, ErrorCode.NOT_IMPLEMENTED)
                # if property_index <
                # TODO validation
                value, = struct.unpack("<H", msg.data)
                property_values[property_index] = value
                resp = make_write_property_response(node_id, property_index, bytes([value & 0xff, value >> 8]))
            else:
                resp = make_error_response(node_id, property_index, opcode, ErrorCode.PROTOCOL_ERROR)
        except:
            traceback.print_exc()
            resp = make_error_response(node_id, property_index, opcode, ErrorCode.INTERNAL_ERROR)

        bus.send(resp)

        # print("Echoing data back to " + str(client_address) + ": " + str(payload))
        # sent = sock.sendto(payload, client_address)


if __name__ == "__main__":
    main()
