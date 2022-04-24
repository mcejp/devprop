import logging
from typing import Optional

from .messages import unpack_id, make_read_property_request, make_read_manifest_request, stringify, \
    make_write_property_request
from .model import ProtocolError, Opcode, SEGMENT_SIZE, NodeId, Direction
from ..can_bus.adapter import StateMachine, Message
from ..manifest import ManifestEnvelope, check_envelope_header

logger = logging.getLogger(__name__)


class ManifestDownload(StateMachine):
    _expected_length: Optional[int]
    _manifest_envelope: bytes
    _node_id: NodeId
    _request_sent_at: Optional[int] = None

    def __init__(self, node_id: NodeId):
        self._expected_length = None
        self._manifest_envelope = b""
        self._node_id = node_id

    def is_finished(self) -> bool:
        return len(self._manifest_envelope) == self._expected_length

    def get_manifest_envelope(self) -> ManifestEnvelope:
        assert self.is_finished()

        return ManifestEnvelope(self._manifest_envelope)

    def get_frame_to_send(self) -> Optional[Message]:
        if self._request_sent_at != len(self._manifest_envelope):
            self._request_sent_at = len(self._manifest_envelope)
            return make_read_manifest_request(self._node_id, len(self._manifest_envelope) // SEGMENT_SIZE)

        return None

    def frame_received(self, msg: Message) -> None:
        node_id, property_index, opcode, direction = unpack_id(msg.id)

        if (direction is Direction.DEVICE_TO_CLIENT and
                node_id == self._node_id and
                opcode == Opcode.READ_MANIFEST and
                property_index == len(self._manifest_envelope) // SEGMENT_SIZE):
            if len(msg.data) > 0:
                if self._expected_length is None or self._manifest_envelope is None:
                    if len(msg.data) != SEGMENT_SIZE:
                        raise ProtocolError(f"Expected {SEGMENT_SIZE}-byte reply")

                    # decode payload header
                    self._expected_length = check_envelope_header(msg.data)
                    self._manifest_envelope = msg.data
                else:
                    self._manifest_envelope += msg.data

                    if len(self._manifest_envelope) < self._expected_length:
                        # expect full segment utilization unless last segment
                        assert len(msg.data) == SEGMENT_SIZE
                    elif len(self._manifest_envelope) > self._expected_length:
                        raise ProtocolError(f"Manifest body too long")
            else:
                raise ProtocolError(f"Expected reply READ_MANIFEST with data, got {stringify(msg)}")


class PropertyQuery(StateMachine):
    node_id: NodeId
    property_index: int
    _get_value: Optional[bytes]
    _set_value: Optional[bytes]
    _opcode: Opcode
    _request_sent: bool = False

    def __init__(self, node_id: NodeId, property_index: int, value: Optional[bytes] = None):
        self.node_id = node_id
        self.property_index = property_index
        self._get_value = None
        self._set_value = value

        self._opcode = Opcode.READ_PROPERTY if value is None else Opcode.WRITE_PROPERTY

    def is_finished(self) -> bool:
        return self._get_value is not None

    def get_value(self):
        assert self.is_finished()

        return self._get_value

    def get_frame_to_send(self) -> Optional[Message]:
        if not self._request_sent:
            self._request_sent = True

            if self._opcode is Opcode.WRITE_PROPERTY:
                return make_write_property_request(self.node_id, self.property_index, self._set_value)
            elif self._get_value is None:
                return make_read_property_request(self.node_id, self.property_index)

        return None

    def frame_received(self, msg: Message) -> None:
        node_id, property_index, opcode, direction = unpack_id(msg.id)

        if (direction is Direction.DEVICE_TO_CLIENT and
                node_id == self.node_id and
                opcode == self._opcode):
            if len(msg.data) > 0:
                self._get_value = msg.data
            else:
                raise ProtocolError(f"Expected reply {self._opcode.name} with data, got {stringify(msg)}")

        # TODO: handle error response
