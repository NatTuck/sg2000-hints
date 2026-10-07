#pragma once
#include <stddef.h>
#include <stdint.h>

/* Bit-bang I2C3's header pads (B20=SDA, B21=SCL) as plain GPIO. */
int i2c_bb_init(uint8_t addr7);

/* Send one transaction: START, addr+W, buf[0..n), STOP. 0 = all ACKed. */
int i2c_bb_write(const uint8_t *buf, size_t n);
