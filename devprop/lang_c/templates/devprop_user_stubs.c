#include "devprop_{{module_name}}.h"

{% for property in manifest.properties %}
{% set T = property.type | C_type -%}

{% if property.readable and not property | is_const %}
{{T}} {{property | getter_function}}(int* error_out) {
    //*error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

{% endif -%}

{% if property.writable %}
{% set T = property.type | C_type %}
{{T}} set_{{property.name | C_identifier}}({{T}} value, int* error_out) {
    *error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

{% endif -%}
{% endfor %}
