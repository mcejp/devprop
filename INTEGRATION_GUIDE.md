## Pre-requisites

- an ECU with a CAN interface and already working basic software
- a supported USB-CAN adapter
- an installation of Python 3.9+
- a working knowledge of C, Git and a command line (shell/PowerShell)

## Introduction

Devprop is a toolkit for definition, discovery and access to named properties in devices -- primarily ECUs on a CAN bus. Devprop is a complete solution consisting of a data model specification, property definition syntax, code generator, CAN-based protocol, C library, and CLI/GUI tooling for PC.

This guide will show you step-by-step how to use it to add named properties to your ECU.

## Preparing the environment

- create a virtual environment & install the Python packages

```sh
python3 -m venv venv
source venv/bin/activate.sh
pip install --editable .[dev]
```

### Configure CAN interface

(If using Ocarina, skip this section completely, as it is configured differently)

Full instructions here: https://python-can.readthedocs.io/en/master/configuration.html#configuration-file

#### Kvaser on Windows

Create the file `%USERPROFILE%/can.conf` with the following contents:

```ini
[default]
interface = kvaser
channel = <the channel to use by default, try 0 if unsure>
bitrate = <the bitrate in bits/s to use by default>
```

You can test your settings by executing `python -m can.viewer`. You should see a visualization of the traffic on the bus.

### Test the package installation

If you configured Python-CAN per the instructions above, the command is simply:

```sh
devscan
```

On the other hand, when using Ocarina, the bus needs to be specified explicitly:

```sh
devscan --bus=ocarina:/dev/ttyUSB0
```

In either case, the output should be "Found 0 nodes". It it fails with an error instead,
this should be fixed before proceeding.

## Writing the device specification

Save this file as `MyDevice.yml`

```yaml
device_name: MyDevice
properties:
  - name: Test.Hello
    type: readonly uint16
    implementation:
      type: const
      raw_value: 123
```

## Generating & integrating the code

To generate the code, we also need to assign a Node ID. Up to 32 Node IDs (0-31) can be present on one bus.
For the purposes of this example, we will use Node ID = 1.

Execute

```sh
devprop-mkmanifest MyDevice.yml --generate-lang=C -O generated --node-id=1
```

A directory called _generated_ will be created. In it, you will find several files.

You should add all of the *.c and *.h files to your project, except for the one named `devprop_MyDevice_stubs.c`.

### Initialization

In the main C file of your project, add

```c
#include "devprop_MyDevice.h"

static dp_Node inst;
```

Later, in the `main` function add this line of code:

```c
dp_node_init_MyDevice(&inst);
```

### Transmission callback

Now it is necessary to implement the callback that the library will use to send messages on the CAN bus.
In a suitable place in your code, you need to implement this function:

```c
void dp_user_send_message_ext(dp_Node* inst,
                              uint32_t id,
                              uint8_t const* data,
                              size_t data_length) {
    // TODO: send message
}
```

The meaning of the arguments should be quite straightforward:
- `inst` will point to your `dp_Node` structure, and is not very important unless you want to implement multiple virtual nodes in a single program
- `id` is the 29-bit Extended CAN ID
- `data` & `data_length` specify the payload. `data_length`, also known as _DLC_, will always be between 0 and 8 inclusive.

The body of the function will naturally depend on the platform that you are using.

Note that Devprop will never initiate communication on its own. A message is only sent as a response to an incoming request (see next step).

### Reception callback

In the part of your code that deals with incoming CAN messages, add this block code,
adapting it to your environment:

```c
bool is_extended_frame = ...;
int id = ...;
uint8_t data[] = ...;
size_t data_length = ...;

if (is_extended_frame) {
    dp_handle_message_ext(&inst, id, data, data_length);
}
```

The meaning of the arguments is analogous to the previous step. Devprop only uses Extended CAN IDs, which is the reason for the `is_extended_frame` check.

Note: If you process received CAN messages in an interrupt handler, it might be wise to implement some buffering to pass them to a main thread first, and only from there to Devprop, mainly to avoid synchronization errors when your property getter/setter callbacks get called in an interrupt context.

And that is it. Now compile your project, flash the ECU, hook the bus up to the PC and we can proceed to the next step.

## Testing the communication

Execute

```sh
devscan --debug
```

Due to the `--debug` argument, there will be a bunch of output. In the beginning, you will see the process of scanning the bus for all the 32 possible Node IDs:

```
INFO:devprop.client:Begin bus scan
DEBUG:devprop.can_bus.python_can_adapter:Tx frame 1ef10000h [                       ] NODE_ID=0 INDEX=0 OPCODE=0-READ_MANIFEST DIR=CLIENT_TO_DEVICE PAYLOAD=
DEBUG:devprop.can_bus.python_can_adapter:Tx frame 1ef10800h [                       ] NODE_ID=1 INDEX=0 OPCODE=0-READ_MANIFEST DIR=CLIENT_TO_DEVICE PAYLOAD=
DEBUG:devprop.can_bus.python_can_adapter:Tx frame 1ef11000h [                       ] NODE_ID=2 INDEX=0 OPCODE=0-READ_MANIFEST DIR=CLIENT_TO_DEVICE PAYLOAD=
...
DEBUG:devprop.can_bus.python_can_adapter:Tx frame 1ef1f800h [                       ] NODE_ID=31 INDEX=0 OPCODE=0-READ_MANIFEST DIR=CLIENT_TO_DEVICE PAYLOAD=
```

If there is no response beyond this, it means the node is either dead, not getting the message, or unable to respond.
You can verify this by placing a breakpoint in `dp_handle_message_ext`. If it is never reached, there is a problem in getting messages out from the PC to the ECU.
If it is, in fact reached, you should step through the code, and see if it reaches `case DPP_READ_MANIFEST:` and eventually `dp_user_send_message_ext`.
If `dp_user_send_message_ext` is called, but no received message is visible in the tool output, there is again a low-level communication problem.

Assuming the best-case scenario, the output will show an initial response received from the ECU:

```
DEBUG:devprop.can_bus.python_can_adapter:Rx frame 1ef00800h [5d f6 a0 8c 2b 00 01 78] NODE_ID=1 INDEX=0 OPCODE=0-READ_MANIFEST DIR=DEVICE_TO_CLIENT PAYLOAD=5d_f6_a0_8c_2b_00_01_78
INFO:devprop.client:Found 1 nodes, downloading manifests
```

Afterwards, the tool proceeds to get to know the node better: it will download its manifest. The manifest is a compressed spreadsheet that is compiled into the firmware
as part of the generated code, and which lets the client understand the defined properties, their types and mapping to physical values.

```
DEBUG:devprop.can_bus.python_can_adapter:Tx frame 1ef10801h [                       ] NODE_ID=1 INDEX=1 OPCODE=0-READ_MANIFEST DIR=CLIENT_TO_DEVICE PAYLOAD=
DEBUG:devprop.can_bus.python_can_adapter:Rx frame 1ef00801h [da f3 ad 74 49 2d cb 4c] NODE_ID=1 INDEX=1 OPCODE=0-READ_MANIFEST DIR=DEVICE_TO_CLIENT PAYLOAD=da_f3_ad_74_49_2d_cb_4c
DEBUG:devprop.can_bus.python_can_adapter:Tx frame 1ef10802h [                       ] NODE_ID=1 INDEX=2 OPCODE=0-READ_MANIFEST DIR=CLIENT_TO_DEVICE PAYLOAD=
DEBUG:devprop.can_bus.python_can_adapter:Rx frame 1ef00802h [4e e5 0a 49 2d 2e d1 f3] NODE_ID=1 INDEX=2 OPCODE=0-READ_MANIFEST DIR=DEVICE_TO_CLIENT PAYLOAD=4e_e5_0a_49_2d_2e_d1_f3
...
DEBUG:devprop.can_bus.python_can_adapter:Rx frame 1ef00806h [0a 74                  ] NODE_ID=1 INDEX=6 OPCODE=0-READ_MANIFEST DIR=DEVICE_TO_CLIENT PAYLOAD=0a_74
DEBUG:devprop.manifest:Manifest header HASH=5df6a08ch LEN=43 VERSION=1
```

At the end of this exchange, `devscan` will present the result in a more user-friendly way.

```
INFO:devprop.client:Finished bus scan
Detected nodes:
- node ID: 1
  device: MyDevice
  property: Property(index=1, name='Test.Hello', type=<PropertyType.UINT16: 'H'>, unit='', offset_str='0', scale_str='1', range_str=('0', '65535'), operations_str='r')
```

The next command to then try is then:

```sh
getprop -d MyDevice Test.Hello
```

And the expected output looks like this:

```
MyDevice@1/Test.Hello = 123
```

## Going forward

A property that has a hard-coded value is not much use. Let's now change the manifest to remove the lines marked below:

```yaml
device_name: MyDevice
properties:
  - name: Test.Hello
    type: readonly uint16
    implementation:         # REMOVE
      type: const           # REMOVE
      raw_value: 123        # REMOVE
```

Re-run the code generation step. If you try to compile your project now, you should get a linker error related to a function called `get_Test_Hello`.
Where does this function come from? Well, it needs to come from the user. If you now open the generated `stubs` file, you will see a prototype of this function:

```c
uint16_t get_Test_Hello(int* error_out) {
    //*error_out = DP_NOT_IMPLEMENTED;
    return 0;
}
```

Copy it into a C file that is included in your project, and change the return value to something more interesting (_456_, for example). We don't need to worry about `error_out` for the moment, so you can delete the commented-out line.

Compile again, flash, and try to repeat the earlier steps (`devscan` and `getprop`). The output of `devscan` should be unchanged, as the interface
of the device is still the same. However, `getprop` will now show the newly changed value.

## Using the GUI tool (Devprop Explorer)

Install the tool similarly to the main library:

```sh
source venv/bin/activate.sh
pip install --editable ./devprop_explorer[dev]
```

Run it:

```sh
devprop-explorer
```
