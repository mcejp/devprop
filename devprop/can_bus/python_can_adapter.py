import time
import logging
from typing import Optional

import can

from .adapter import BusAdapter, Message
from ..protocol_can_ext_v1.messages import stringify

logger = logging.getLogger(__name__)


class PythonCanAdapter(BusAdapter):
    _bus: can.BusABC

    def __init__(self):
        self._bus = can.Bus()

    def receive(self, deadline: Optional[float] = None) -> Message:
        if deadline is not None:
            timeout = deadline - time.monotonic()

            if timeout < 0:
                raise TimeoutError()
        else:
            timeout = None

        message = self._bus.recv(timeout=timeout)

        if message is None:
            raise TimeoutError()

        assert message.is_extended_id

        msg = Message(id=message.arbitration_id, data=bytes(message.data))

        logger.debug("Rx frame %08xh [%-23s] %s", msg.id, msg.data.hex(" "), stringify(msg))

        return msg

    def send(self, msg: Message):
        logger.debug("Tx frame %08xh [%-23s] %s", msg.id, msg.data.hex(" "), stringify(msg))

        self._bus.send(can.Message(arbitration_id=msg.id, data=msg.data, is_extended_id=True))
