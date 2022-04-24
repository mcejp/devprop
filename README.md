HOWTO:

```
# set up vcan
cat <<EOT >> ~/can.conf
[default]
interface = socketcan
channel = vcan0
bitrate = 500000
EOT

sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 up

python3 -m venv venv
./venv/bin/pip install --editable .[dev]
./venv/bin/pip install --editable ./devprop-ocarina[dev]

make ams_props.bin
./venv/bin/devprop-test-server ams_props.bin 7 &

./venv/bin/devscan --debug
./venv/bin/getprop -d FSE10.FSB Ocp.Threshold.Ams
./venv/bin/setprop -d FSE10.FSB Ocp.Threshold.Ams 5.12 

# manifest compiler & code generator
./venv/bin/devprop-mkmanifest examples/FSE10.HELLO.yml --generate-lang=C -O lang_c --node-id=1

# GUI WIP
./venv/bin/pip install PySide2
./venv/bin/python3 config-tool.py &
```
