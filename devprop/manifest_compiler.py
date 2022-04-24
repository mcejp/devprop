#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path

from .manifest import add_envelope, HEADER_LENGTH, parse_manifest_draft_csv, parse_manifest_yaml, serialize_manifest_draft_csv, validate_manifest, DRAFT_CSV_ZLIB
from .protocol_can_ext_v1.model import SEGMENT_SIZE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("-o", dest="output", type=Path)
    parser.add_argument("-O", dest="output_dir", type=Path, default=Path("."))
    parser.add_argument("--generate-lang", choices=["C"])
    parser.add_argument("--node-id", type=int)
    args = parser.parse_args()

    logging.basicConfig()

    if args.path.suffix.lower() in {".yml", ".yaml"}:
        # YAML manifest
        with open(args.path, "rt") as f:
            manifest = parse_manifest_yaml(f)

        manifest_payload = serialize_manifest_draft_csv(manifest)
    else:
        # CSV manifest
        with open(args.path, "rb") as f:
            manifest_payload = f.read()

        # validate & generate HTML doc
        # TODO
        manifest = parse_manifest_draft_csv(manifest_payload)

    errors = validate_manifest(manifest)

    for error in errors:
        logging.error("manifest validation error: %s", error)

    envelope = add_envelope(manifest_payload, DRAFT_CSV_ZLIB)

    if args.output:
        with open(args.output, "wb") as f:
            f.write(envelope)

    uncompressed_length = HEADER_LENGTH + len(manifest_payload)

    print("(uncompressed wire length:", uncompressed_length, "bytes =", (uncompressed_length + SEGMENT_SIZE - 1) // SEGMENT_SIZE, "segments)")
    print("manifest wire length:", len(envelope), "bytes =", (len(envelope) + SEGMENT_SIZE - 1) // SEGMENT_SIZE, "segments")

    if args.generate_lang == "C":
        assert args.node_id is not None

        from . import lang_c

        module_name = lang_c.C_identifier(manifest.device_name)

        args.output_dir.mkdir(exist_ok=True)
        lang_c.generate(manifest=manifest, envelope=envelope, module_name=module_name, node_id=args.node_id, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
