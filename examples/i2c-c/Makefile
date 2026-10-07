# Cross-build the Linux I2C examples for the Oz64 (riscv64) and copy them over.
# Use 'make CC=...' to override.
CC      := riscv64-linux-gnu-gcc
CFLAGS  ?= -static -O2 -Wall -Wextra
BOARD   ?= debian@oz64-toad
BINS     = linux-i2c-dev linux-mmap-bitbang

all: $(BINS)

linux-i2c-dev: linux-i2c-dev.c ssd1306.h font5x7.h
	$(CC) $(CFLAGS) -o $@ $<

linux-mmap-bitbang: linux-mmap-bitbang.c ssd1306.h font5x7.h
	$(CC) $(CFLAGS) -o $@ $<

deploy: all
	scp $(BINS) $(BOARD):/tmp/

clean:
	rm -f $(BINS)

.PHONY: all deploy clean
