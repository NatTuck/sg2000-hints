#pragma once
#include <stddef.h>
#include <stdint.h>

/* Initialise I2C3 as a master and target `addr7`. Returns 0 on success. */
int i2c_dw_init(uint8_t addr7);

/* Send one transaction: START, addr+W, buf[0..n), STOP. 0 = all ACKed. */
int i2c_dw_write(const uint8_t *buf, size_t n);
