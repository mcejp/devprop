import logging

from devprop.can_bus.transport_plugin import get_adapter
from devprop.client import Client


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bus")
    parser.add_argument("-D", "--debug", dest="debug", action="store_true")
    parser.add_argument("-T", dest="timeout_sec", type=float, default=1)
    args = parser.parse_args()

    logging.basicConfig()

    if args.debug:
        logging.getLogger("devprop").setLevel(logging.DEBUG)

    cl = Client(get_adapter(args.bus))

    nodes = cl.enumerate_nodes(timeout_sec=args.timeout_sec)

    print("Detected nodes:")

    for node_id, node in nodes.items():
        print(f"- node ID: {node_id}")
        print(f"  device: {node.device_name}")
        for prop in node.properties:
            print(f"  property: {prop}")


if __name__ == "__main__":
    main()
