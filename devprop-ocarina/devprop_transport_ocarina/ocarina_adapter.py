import time
import logging
from typing import Optional

from devprop.can_bus.adapter import BusAdapter, Message
from devprop.protocol_can_ext_v1.messages import stringify

from . import ocarina

logger = logging.getLogger(__name__)


class OcarinaAdapter(BusAdapter):
    def __init__(self, port: str):
        self._ocarina = ocarina.Ocarina(port)

        # Not clear if it is our business to set these...
        self._ocarina.set_bitrate_auto()
        self._ocarina.set_silent(False)
        self._ocarina.set_loopback(False)

        self._ocarina.set_message_forwarding(True)

    def receive(self, deadline: Optional[float] = None) -> Message:
        while True:
            if deadline is not None:
                timeout = deadline - time.monotonic()

                if timeout < 0:
                    raise TimeoutError()
            else:
                timeout = None

            event = self._ocarina.read_event(timeout=timeout)

            if isinstance(event, ocarina.CanMsgEvent) and event.id.type is ocarina.IDTYPE.EXT:
                msg = Message(id=event.id.value, data=event.data)
                break

        logger.debug("Rx frame %08xh [%-23s] %s", msg.id, msg.data.hex(" "), stringify(msg))

        return msg

    def send(self, msg: Message):
        logger.debug("Tx frame %08xh [%-23s] %s", msg.id, msg.data.hex(" "), stringify(msg))

        self._ocarina.send_message_ext(msg.id, msg.data)
