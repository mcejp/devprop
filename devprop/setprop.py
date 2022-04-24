import logging

from devprop.can_bus.transport_plugin import get_adapter
from devprop.client import Client


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bus")
    parser.add_argument("-D", "--debug", dest="debug", action="store_true")
    parser.add_argument("-T", dest="timeout_sec", type=float, default=1)
    parser.add_argument("-d", dest="device", required=True)
    parser.add_argument("property")
    parser.add_argument("value", type=float)
    args = parser.parse_args()

    logging.basicConfig()

    if args.debug:
        logging.getLogger("devprop").setLevel(logging.DEBUG)

    cl = Client(get_adapter(args.bus))

    nodes = cl.enumerate_nodes(timeout_sec=args.timeout_sec)

    # find device
    node, = [node for node in nodes.values() if node.device_name == args.device]

    # find property
    property, = [prop for prop in node.properties if prop.name == args.property]

    value = cl.set_property(node, property, args.value, timeout_sec=args.timeout_sec)

    print(node.get_property_path(property), "=", value, property.unit)


if __name__ == "__main__":
    main()
