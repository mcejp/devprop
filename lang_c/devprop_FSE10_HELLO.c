#include "devprop_FSE10_HELLO.h"

uint16_t get_Test_Uint16_RO(int* error_out);
uint16_t get_Test_Uint16_RW(int* error_out);
uint16_t set_Test_Uint16_RW(uint16_t value, int* error_out);
uint16_t set_Test_Uint16_WO(uint16_t value, int* error_out);
uint32_t get_Test_Uint32_RW(int* error_out);
uint32_t set_Test_Uint32_RW(uint32_t value, int* error_out);
uint8_t get_Test_Uint8_RW(int* error_out);
uint8_t set_Test_Uint8_RW(uint8_t value, int* error_out);
static uint8_t get_Test_Uint8_Const(int* error_out);

static const dp_Property property_table[] = {
    {DP_UINT16, (dp_GenericCallback) &get_Test_Uint16_RO,    NULL},
    {DP_UINT16, (dp_GenericCallback) &get_Test_Uint16_RW,    (dp_GenericCallback) &set_Test_Uint16_RW},
    {DP_UINT16, NULL,                                        (dp_GenericCallback) &set_Test_Uint16_WO},
    {DP_UINT32, (dp_GenericCallback) &get_Test_Uint32_RW,    (dp_GenericCallback) &set_Test_Uint32_RW},
    {DP_UINT8,  (dp_GenericCallback) &get_Test_Uint8_RW,     (dp_GenericCallback) &set_Test_Uint8_RW},
    {DP_UINT8,  (dp_GenericCallback) &get_Test_Uint8_Const,  NULL},
};

static const uint8_t manifest_bytes[] = {
    0x18, 0x4B, 0x10, 0xD7, 0x6D, 0x00, 0xF1, 0x78, 0xDA, 0x73, 0x0B, 0x76, 0x35, 0x34, 0xD0, 0xF3,
    0x70, 0xF5, 0xF1, 0xF1, 0xE7, 0x0A, 0x49, 0x2D, 0x2E, 0xD1, 0x0B, 0xCD, 0xCC, 0x2B, 0x31, 0x34,
    0xD3, 0x0B, 0xF2, 0xD7, 0xF1, 0xD0, 0xD1, 0x31, 0xD0, 0x31, 0x04, 0x62, 0x33, 0x53, 0x53, 0x63,
    0x53, 0x9D, 0x22, 0x54, 0xF9, 0x70, 0x0C, 0xF9, 0x72, 0x14, 0x05, 0xE1, 0x18, 0x06, 0x20, 0xC9,
    0x1B, 0x1B, 0x81, 0x0C, 0xF0, 0x84, 0xC9, 0x1B, 0x19, 0xC0, 0x00, 0x8A, 0x29, 0x16, 0x20, 0x45,
    0x4E, 0x70, 0x45, 0xA6, 0xA6, 0x68, 0xB2, 0xCE, 0xF9, 0x79, 0xC5, 0x25, 0x40, 0x05, 0x29, 0xA9,
    0xE9, 0xCE, 0x40, 0x33, 0x74, 0x0C, 0xF4, 0x0C, 0x41, 0x94, 0x89, 0xA9, 0x1E, 0xC8, 0xB5, 0x00,
    0x84, 0x94, 0x39, 0x13,
};

void dp_node_init_FSE10_HELLO(dp_Node* inst) {
    dp_node_init(inst, DP_NODE_ID_FSE10_HELLO,
                 manifest_bytes, sizeof(manifest_bytes), property_table,
                 sizeof(property_table) / sizeof(property_table[0]));
}

static uint8_t get_Test_Uint8_Const(int* error_out) {
    return 77;
}
