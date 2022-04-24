from pathlib import Path

from devprop.model import Manifest, Property, PropertyType

import jinja2


def C_identifier(input: str):
    return input.replace(".", "_")


class Codegen:
    def __init__(self, manifest: Manifest, envelope: bytes, module_name: str, node_id: int):
        self._manifest = manifest
        self._module_name = module_name
        self._envelope = envelope

        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=jinja2.StrictUndefined,
        )

        def C_const(type: PropertyType):
            return {
                PropertyType.UINT8: "DP_UINT8",
                PropertyType.UINT16: "DP_UINT16",
                PropertyType.UINT32: "DP_UINT32",
            }[type]

        def C_type(type: PropertyType):
            return {
                PropertyType.UINT8: "uint8_t",
                PropertyType.UINT16: "uint16_t",
                PropertyType.UINT32: "uint32_t",
            }[type]

        def const_raw_value(prop: Property):
            implementation = prop.additional_attributes.get("implementation", {})
            # TODO: type + range check
            return implementation["raw_value"]

        def getter_function_name(prop: Property):
            return "get_" + C_identifier(prop.name)

        def is_const(prop: Property):
            # TODO: all this validation ought to be done in a pre-pass
            type = prop.additional_attributes.get("implementation", {}).get("type")
            assert type in {"const", None}
            if type == "const":
                if prop.operations_str != "r":
                    raise Exception(f"Property {prop.name} with implementation.type = 'const' must be 'readonly'")
            return type == "const"

        def to_array_literal(blob: bytes, bytes_per_row: int):
            s = ""
            for offset in range(0, len(blob), bytes_per_row):
                s += "    " + ", ".join(f"0x{b:02X}" for b in blob[offset:offset + bytes_per_row]) + ",\n"
            return s

        def setter_function(prop: Property):
            return "set_" + C_identifier(prop.name)

        self._env.filters["C_const"] = C_const
        self._env.filters["C_identifier"] = C_identifier
        self._env.filters["C_type"] = C_type
        self._env.filters["const_raw_value"] = const_raw_value
        self._env.filters["getter_function"] = getter_function_name
        self._env.filters["is_const"] = is_const
        self._env.filters["to_array_literal"] = to_array_literal
        self._env.filters["setter_function"] = setter_function

        self._env.globals["device_name"] = C_identifier(manifest.device_name)
        self._env.globals["envelope"] = self._envelope
        self._env.globals["manifest"] = manifest
        self._env.globals["module_name"] = self._module_name
        self._env.globals["node_id"] = node_id

    def generate(self, dir: Path):
        paths = [
            ("devprop_user.c", f"devprop_{self._module_name}.c"),
            ("devprop_user.h", f"devprop_{self._module_name}.h"),
            ("devprop_user_stubs.c", f"devprop_{self._module_name}_stubs.c"),
        ]

        for template_name, out in paths:
            with open(dir / out, "wt") as f:
                template = self._env.get_template(template_name)
                f.write(template.render())


def generate(manifest: Manifest, envelope: bytes, module_name: str, node_id: int, output_dir: Path):
    codegen = Codegen(manifest, envelope, module_name, node_id)
    codegen.generate(output_dir)
