import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from devprop.can_bus.adapter import BusAdapter, execute_state_machine, Message
from .manifest import parse_enveloped_manifest
from .model import Property, Manifest
from .property import decode_value, encode_value
from .protocol_can_ext_v1.messages import unpack_id, make_read_manifest_request
from .protocol_can_ext_v1.model import Direction, MAX_NODE_ID, ProtocolError, Opcode, NodeId
from .protocol_can_ext_v1.state_machines import ManifestDownload, PropertyQuery

logger = logging.getLogger(__name__)


@dataclass
class Node:
    node_id: NodeId
    manifest: Manifest

    @property
    def address_str(self) -> str:
        return f"{self.node_id:d}"

    @property
    def device_name(self) -> str:
        return self.manifest.device_name

    def get_property_path(self, property: Property):
        return f"{self.name}/{property.name}"

    @property
    def name(self) -> str:
        return f"{self.manifest.device_name}@{self.address_str}"

    @property
    def properties(self) -> List[Property]:
        return self.manifest.properties


class Client:
    def __init__(self, bus: BusAdapter):
        self.bus = bus

    def enumerate_nodes(self, timeout_sec: float) -> Dict[NodeId, Node]:
        logger.info("Begin bus scan")

        for node_id in range(MAX_NODE_ID):
            self.bus.send(make_read_manifest_request(node_id=node_id, segment=0))

        # receive replies

        candidate_nodes: Dict[NodeId, Message] = {}
        nodes: Dict[NodeId, Node] = {}

        deadline = time.monotonic() + timeout_sec

        while True:
            try:
                msg = self.bus.receive(deadline=deadline)
                node_id, property_index, opcode, direction = unpack_id(msg.id)

                if opcode is Opcode.READ_MANIFEST and property_index == 0 and direction is Direction.DEVICE_TO_CLIENT:
                    # Ping ok, queue to download manifest
                    candidate_nodes[node_id] = msg
            except ProtocolError as ex:
                logger.error("Protocol error: %s", str(ex))
            except TimeoutError:
                break

        logger.info("Found %d nodes, downloading manifests", len(candidate_nodes))

        for node_id, initial_reply in candidate_nodes.items():
            md = ManifestDownload(node_id=node_id)
            md.frame_received(initial_reply)

            try:
                execute_state_machine(self.bus, md, deadline=time.monotonic() + timeout_sec)
                mf_blob = md.get_manifest_envelope()

                mf = parse_enveloped_manifest(mf_blob)
                # print(mf)

                nodes[node_id] = Node(node_id, mf)
            except ProtocolError as ex:
                logger.error("Protocol error node_id %d: %s", node_id, str(ex))
            except Exception as ex:
                logger.exception(ex)

        logger.info("Finished bus scan")
        return nodes

    def get_property(self, node: Node, property: Property, timeout_sec: float) -> float:
        result, = self.query_properties([(node, property)], timeout_sec=timeout_sec)

        return decode_value(property, result)

    def set_property(self, node: Node, property: Property, value: float, timeout_sec: float) -> Any:
        encoded_value = encode_value(property, value)

        pq = PropertyQuery(node.node_id, property.index, encoded_value)

        execute_state_machine(self.bus, pq, time.monotonic() + timeout_sec)

        logger.debug("%s --> %s", property.name, pq.get_value())
        return decode_value(property, pq.get_value())

    def query_properties(self, properties: List[Tuple[Node, Property]], timeout_sec: float) -> List[Optional[bytes]]:
        resp = []

        for dev, prop in properties:
            # print(dev, prop)

            # Query property
            pq = PropertyQuery(dev.node_id, prop.index)

            try:
                execute_state_machine(self.bus, pq, time.monotonic() + timeout_sec)

                logger.debug("%s --> %s", prop.name, pq.get_value())
                resp.append(pq.get_value())
            except ProtocolError as ex:
                logger.error("Protocol error device %s: %s", dev.name, str(ex))
                resp.append(None)
            except Exception as ex:
                logger.exception(ex)
                resp.append(None)

        return resp
