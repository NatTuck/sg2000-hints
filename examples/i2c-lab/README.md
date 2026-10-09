# I2C Display Lab (CS4250, 10-09)

Programs for the CS4250 "10-09 I2C Display Lab", targeting the SG2000 boards
(Pine64 Oz64 / Milk-V Duo S) with an ELEGOO SSD1306 128x64 OLED on bus **IIC1**
(header pin 11 = SDA, pin 13 = SCL, `/dev/i2c-1` @ `0x3C`).

## Python (Linux side)

Copy `ssd1306.py` and `oled.py` to the board, then run:

```sh
sudo python3 oled.py "your text"
```

## Arduino (C906 core via remoteproc)

```sh
cd oled-text && arduino-cli compile --fqbn sophgo:SG200X:duos   # or :oz64
```

Load the ELF via remoteproc: copy it into `/lib/firmware/`, write the filename to
`/sys/class/remoteproc/remoteproc0/firmware`, then `start` it via
`/sys/class/remoteproc/remoteproc0/state`.
