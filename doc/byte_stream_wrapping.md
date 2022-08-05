## Wrapping CAN messages in a byte stream

This is a quick-and-dirty provisional solution until a better protocol is devised.
COBS encoding is used to remove all 0-bytes from the frame, and this character code
is used as frame delimiter, permitting resynchronization at any time.

It can be used over any bi-directional byte stream medium (UART, USB CDC, TCP...)

```
logical_frame   = uint32_le(msg.id) + msg.payload
frame+crc       = logical_frame + crc16_kermit(logical_frame)
wire_frame      = \x00 + COBS_encode(frame+crc) + \x00
```
