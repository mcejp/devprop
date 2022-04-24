#ifndef DEVPROP_{{module_name}}_H
#define DEVPROP_{{module_name}}_H

#include "devprop.h"

enum { DP_NODE_ID_{{device_name}} = {{node_id}} };

{% for property in manifest.properties %}
enum { INDEX_{{property.name | C_identifier | upper}} = {{property.index}} };
{% endfor %}

void dp_node_init_{{device_name}}(dp_Node* inst_out);

#endif
