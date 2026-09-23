// GpioAsm — drive the J3 pin 7 LED (XGPIOB18) from inline RISC-V assembly.
//
// Stage 1: pinMode() does the one-time pinmux + direction setup; the
// per-cycle toggling is done with explicit loads/stores in asm.
//
// XGPIOB (GPIO bank 1) is memory-mapped at 0x03021000:
//   +0x00  SWPORTA_DR   output data
//   +0x04  SWPORTA_DDR  direction (1 = output)
//   +0x50  EXT_PORTA    pad input (read-only)
// Pin 7 = VIVO_D3 = XGPIOB_18, so the bit is 18.

#define GPIOB_BASE 0x03021000UL
#define LED_BIT    (1u << 18)

void setup() {
  pinMode(7, OUTPUT);  // mux VIVO_D3 -> XGPIOB_18 and set direction
}

// Set the pin: a single store to the data register.
static inline void led_high() {
  uint32_t base = GPIOB_BASE;
  uint32_t bit = LED_BIT;
  asm volatile("sw %1, 0(%0)" : : "r"(base), "r"(bit) : "memory");
}

// Clear the pin: read-modify-write the data register.
static inline void led_low() {
  uint32_t base = GPIOB_BASE;
  uint32_t bit = LED_BIT;
  asm volatile(
      "lw  t0, 0(%0)\n\t"   // t0 = current output register
      "not t1, %1\n\t"      // t1 = ~bit
      "and t0, t0, t1\n\t"  // clear the bit
      "sw  t0, 0(%0)"       // write it back
      : : "r"(base), "r"(bit) : "t0", "t1", "memory");
}

void loop() {
  led_high();
  delay(50);
  led_low();
  delay(50);
}
