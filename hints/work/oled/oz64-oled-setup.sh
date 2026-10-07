#!/bin/sh
# Route SoC IIC3 to the Oz64 26-pin GPIO header so the SSD1306 OLED works.
#
#   header pin 3 = XGPIOB[20] = SDA
#   header pin 5 = XGPIOB[21] = SCL
#   -> Linux /dev/i2c-3, address 0x3c
#
# The stock FSBL pinmux routes IIC3 to pads A5/A6, which are NOT on the header.
# If both sets of pads stay muxed to IIC3 the bus does not work, so free A5/A6
# first, then mux the header pads. Must run as root.
set -e

cvi-pinmux -w IIC3_SCL/XGPIOA_5
cvi-pinmux -w IIC3_SDA/XGPIOA_6
duo-pinmux -w B20/IIC3_SDA
duo-pinmux -w B21/IIC3_SCL

echo "Oz64 header IIC3 ready: /dev/i2c-3 @ 0x3c (pin3=SDA, pin5=SCL)"
