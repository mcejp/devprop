#include "devprop_{{module_name}}.h"

{% for property in manifest.properties %}
{% set T = property.type | C_type -%}

{% if property.readable %}
{% if property | is_const %}static {% endif %}{{T}} {{property | getter_function}}(int* error_out);
{% endif -%}

{% if property.writable %}
{% set T = property.type | C_type %}
{{T}} set_{{property.name | C_identifier}}({{T}} value, int* error_out);
{% endif %}
{% endfor %}

static const dp_Property property_table[] = {
{% for property in manifest.properties %}
    {{"{"}}{{"%-11s" | format(property.type | C_const + ", ")}}
    {%- if property.readable -%}
    {{"%-45s" | format("(dp_GenericCallback) &" + property | getter_function + ", ")}}
    {%- else -%}
    {{"%-45s" | format("NULL, ")}}
    {%- endif -%}
    {%- if property.writable -%}
    {{"(dp_GenericCallback) &" + property | setter_function}}
    {%- else -%}
    {{"NULL"}}
    {%- endif -%}{{"}"}},
{% endfor %}
};

static const uint8_t manifest_bytes[] = {
{{ envelope | to_array_literal(16) -}}
};

void dp_node_init_{{device_name}}(dp_Node* inst) {
    dp_node_init(inst, DP_NODE_ID_{{device_name}},
                 manifest_bytes, sizeof(manifest_bytes), property_table,
                 sizeof(property_table) / sizeof(property_table[0]));
}

{% for property in manifest.properties %}
{% set T = property.type | C_type %}
{% if property | is_const %}
static {{T}} {{property | getter_function}}(int* error_out) {
    return {{ property | const_raw_value }};
}
{% endif %}
{% endfor %}
