#include "devprop_FSE10_HELLO.h"
#include "devprop_can_ext_v1.h"

#include <stdio.h>

static void print_message(const char* prefix, uint32_t id, uint8_t const* data,size_t data_length);
static void mock_received_message(dp_Node* inst, uint32_t id, uint8_t const* data, size_t data_length);

int main() {
    uint32_t id;

    // init device
    static dp_Node inst;
    dp_node_init_FSE10_HELLO(&inst);

    // simulate client request: READ MANIFEST[0]
    id = dpp_make_id(DPP_CLIENT_TO_DEVICE, DP_NODE_ID_FSE10_HELLO, DPP_READ_MANIFEST, 0);
    mock_received_message(&inst, id, NULL, 0);

    // simulate client request: READ PROPERTY [1]
    id = dpp_make_id(DPP_CLIENT_TO_DEVICE, DP_NODE_ID_FSE10_HELLO, DPP_READ_PROPERTY, INDEX_TEST_UINT16_RO);
    mock_received_message(&inst, id, NULL, 0);

    // simulate client request: WRITE PROPERTY [1] (should fail)
    id = dpp_make_id(DPP_CLIENT_TO_DEVICE, DP_NODE_ID_FSE10_HELLO, DPP_WRITE_PROPERTY, INDEX_TEST_UINT16_RO);
    uint8_t dummy_data[] = {0x12, 0x34};
    mock_received_message(&inst, id, dummy_data, sizeof(dummy_data));

    // simulate client request: READ PROPERTY [2]
    id = dpp_make_id(DPP_CLIENT_TO_DEVICE, DP_NODE_ID_FSE10_HELLO, DPP_READ_PROPERTY, INDEX_TEST_UINT16_RW);
    mock_received_message(&inst, id, NULL, 0);

    // simulate client request: WRITE PROPERTY [2] (should succeed)
    id = dpp_make_id(DPP_CLIENT_TO_DEVICE, DP_NODE_ID_FSE10_HELLO, DPP_WRITE_PROPERTY, INDEX_TEST_UINT16_RW);
    mock_received_message(&inst, id, dummy_data, sizeof(dummy_data));

    // simulate client request: READ PROPERTY [2]
    id = dpp_make_id(DPP_CLIENT_TO_DEVICE, DP_NODE_ID_FSE10_HELLO, DPP_READ_PROPERTY, INDEX_TEST_UINT16_RW);
    mock_received_message(&inst, id, NULL, 0);

    return 0;
}

// required user callback(s)

void dp_user_send_message_ext(dp_Node* inst, uint32_t id, uint8_t const* data, size_t data_length) {
    print_message("TX", id, data, data_length);
}

// property stubs

uint16_t get_Test_Uint16_RO(int* error_out) {
    //*error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

static uint16_t Test_Uint16_RW;

uint16_t get_Test_Uint16_RW(int* error_out) {
    return Test_Uint16_RW;
}

uint16_t set_Test_Uint16_RW(uint16_t value, int* error_out) {
    Test_Uint16_RW = value;
    return value;
}

uint16_t set_Test_Uint16_WO(uint16_t value, int* error_out) {
    *error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

uint32_t get_Test_Uint32_RW(int* error_out) {
    //*error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

uint32_t set_Test_Uint32_RW(uint32_t value, int* error_out) {
    *error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

uint8_t get_Test_Uint8_RW(int* error_out) {
    //*error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

uint8_t set_Test_Uint8_RW(uint8_t value, int* error_out) {
    *error_out = DP_NOT_IMPLEMENTED;
    return 0;
}

// test utility functions

static void print_message(const char* prefix, uint32_t id, uint8_t const* data,size_t data_length) {
    printf("%s MSG_ID=%08X PAYLOAD=[", prefix, id);
    for (size_t i = 0; i < data_length; i++) {
        printf("%02X ", data[i]);
    }
    for (size_t i = data_length; i < 8; i++) {
        printf("   ");
    }

    int property_index = (id & 0xFF);
    int opcode = (id >> 8) & 7;
    int node_id = (id >> 11) & 31;
    int dir = (id >> 16) & 1;

    static const char* opcode_names[] = {
        "READ_MANIFEST",
        "READ_PROPERTY",
        "WRITE_PROPERTY",
        "3",
        "4",
        "5",
        "6",
        "ERROR",
    };

    printf("] DIR=%-8s NODE_ID=%d OPCODE=%-14s INDEX=%d", dir == DPP_CLIENT_TO_DEVICE ? "Request" : "Response", node_id, opcode_names[opcode], property_index);

    if (opcode == DPP_ERROR && data_length == 2) {
        printf(" FAILED-OPCODE=%d ERROR-CODE=%d", data[0], data[1]);
    }

    printf("\n");
}

static void mock_received_message(dp_Node* inst, uint32_t id, uint8_t const* data, size_t data_length) {
    print_message("RX", id, data, data_length);

    dp_handle_message_ext(inst, id, data, data_length);
}
