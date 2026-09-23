// GpioAsmRaw — drive the J3 pin 7 LED (XGPIOB18) with raw register stores.
//
// Stage 2: no Arduino GPIO API at all. The pad mux, the direction bit and
// the output bit are all written with inline asm. (delay() is still used for
// timing; only the GPIO path is raw.)
//
// Registers used:
//   pinmux for VIVO_D3  0x03001000 + 0x150 = 0x03001150, bits[2:0] = 3 (GPIO)
//   XGPIOB data dir     0x03021004, bit 18
//   XGPIOB output data  0x03021000, bit 18

#define PINMUX_VIVO_D3 0x03001150UL
#define GPIOB_DR       0x03021000UL
#define GPIOB_DDR      0x03021004UL
#define LED_BIT        (1u << 18)
#define MUX_GPIO       0x3u

static inline uint32_t raw_read(uint32_t addr) {
  uint32_t v;
  asm volatile("lw %0, 0(%1)" : "=r"(v) : "r"(addr) : "memory");
  return v;
}

static inline void raw_write(uint32_t addr, uint32_t val) {
  asm volatile("sw %1, 0(%0)" : : "r"(addr), "r"(val) : "memory");
}

void setup() {
  // Select the GPIO function on VIVO_D3, preserving pull/drive/speed bits.
  uint32_t mux = raw_read(PINMUX_VIVO_D3);
  mux = (mux & ~0x7u) | MUX_GPIO;
  raw_write(PINMUX_VIVO_D3, mux);

  // Configure XGPIOB18 as an output.
  raw_write(GPIOB_DDR, raw_read(GPIOB_DDR) | LED_BIT);
}

void loop() {
  raw_write(GPIOB_DR, raw_read(GPIOB_DR) | LED_BIT);  // high
  delay(50);
  raw_write(GPIOB_DR, raw_read(GPIOB_DR) & ~LED_BIT); // low
  delay(50);
}
