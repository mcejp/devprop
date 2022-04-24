#ifndef DEVPROP_FSE10_HELLO_H
#define DEVPROP_FSE10_HELLO_H

#include "devprop.h"

enum { DP_NODE_ID_FSE10_HELLO = 1 };

enum { INDEX_TEST_UINT16_RO = 1 };
enum { INDEX_TEST_UINT16_RW = 2 };
enum { INDEX_TEST_UINT16_WO = 3 };
enum { INDEX_TEST_UINT32_RW = 4 };
enum { INDEX_TEST_UINT8_RW = 5 };
enum { INDEX_TEST_UINT8_CONST = 6 };

void dp_node_init_FSE10_HELLO(dp_Node* inst_out);

#endif