import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    id: int
    data: bytes


class BusAdapter(ABC):
    @abstractmethod
    def receive(self, deadline: Optional[float] = None) -> Message:
        ...

    @abstractmethod
    def send(self, msg: Message) -> None:
        ...


class StateMachine(ABC):
    def is_finished(self) -> bool:
        raise NotImplementedError()

    def get_frame_to_send(self) -> Optional[Message]:
        raise NotImplementedError()

    def frame_received(self, msg: Message) -> None:
        raise NotImplementedError()


def execute_state_machine(bus, sm: StateMachine, deadline: float) -> None:
    while not sm.is_finished():
        if time.monotonic() > deadline:
            raise TimeoutError()

        frame_to_send = sm.get_frame_to_send()

        if frame_to_send is not None:
            bus.send(frame_to_send)

        # It's not that it would be fundamentally impossible to burst multiple frames at once,
        # but for now there is no need and we don't handle it well
        assert sm.get_frame_to_send() is None

        msg = bus.receive(deadline)

        sm.frame_received(msg)
