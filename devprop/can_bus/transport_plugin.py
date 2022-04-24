import sys
from typing import Optional

from .adapter import BusAdapter


class TransportPluginNotFoundError(Exception):
    def __init__(self, transport_name):
        self.transport_name = transport_name


def get_adapter(bus_dsn: Optional[str] = None) -> BusAdapter:
    if not bus_dsn:
        from .python_can_adapter import PythonCanAdapter

        # TODO: try to scan for Ocarina?

        return PythonCanAdapter()
    else:
        # Look for appropriate plug-in
        transport_name, parameters = bus_dsn.split(":", 1)

        if sys.version_info < (3, 10):
            from importlib_metadata import entry_points
        else:
            # We *must not* attempt this pre-3.10, as the built-in package has an incompatible API
            from importlib.metadata import entry_points

        discovered_plugins = entry_points(group="devprop.can_bus.adapter")

        try:
            entry_point = discovered_plugins[transport_name]
        except KeyError:
            raise TransportPluginNotFoundError(transport_name) from None

        adapter_factory = entry_point.load()

        return adapter_factory(parameters)

        # raise ValueError(bus_dsn)
