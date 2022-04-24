all: test_offline

test_offline: devprop_can_ext_v1.o devprop_FSE10_HELLO.o test_offline.o
	$(CC) -o $@ $^
