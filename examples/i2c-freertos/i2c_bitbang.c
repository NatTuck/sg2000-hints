/* i2c_bitbang.c - software I2C on the SG2000 little core, no controller.
 *
 * REASONED, not board-tested. Same idea as the verified Linux
 * examples/i2c-c/linux-mmap-bitbang.c, but in M-mode with direct MMIO and a
 * busy-wait instead of nanosleep. Useful when the DesignWare block's clock is
 * gated and no vendor driver is available.
 *
 *   header pin 3 = XGPIOB[20] -> SDA
 *   header pin 5 = XGPIOB[21] -> SCL
 */
#include "i2c_bitbang.h"

#define MUX_B20 0x03001158UL
#define MUX_B21 0x0300115CUL
#define GPIOB_BASE 0x03021000UL
#define SDA 20
#define SCL 21

#define FUNC_GPIO 3u

#define DR (GPIOB_BASE + 0x00)
#define DDR (GPIOB_BASE + 0x04)
#define EXT (GPIOB_BASE + 0x50)

static inline uint32_t rd(uint32_t a) { return *(volatile uint32_t *)a; }
static inline void wr(uint32_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

static void pad_out(int bit, int high) {
    uint32_t d = rd(DR);
    if (high)
        d |= (1u << bit);
    else
        d &= ~(1u << bit);
    wr(DR, d);
    wr(DDR, rd(DDR) | (1u << bit));
}
static void pad_release(int bit) { wr(DDR, rd(DDR) & ~(1u << bit)); }
static void sda_low(void) { pad_out(SDA, 0); }
static void sda_rel(void) { pad_release(SDA); }
static void scl_low(void) { pad_out(SCL, 0); }
static void scl_rel(void) { pad_release(SCL); }
static int sda_val(void) {
    pad_release(SDA);
    return (int)((rd(EXT) >> SDA) & 1u);
}

/* ~5 us at 700 MHz; tune against mtime for real timing analysis. */
static void half(void) {
    for (volatile int i = 0; i < 1750; i++)
        ;
}

static void start(void) {
    sda_rel();
    scl_rel();
    half();
    sda_low();
    half();
    scl_low();
    half();
}
static void stop(void) {
    sda_low();
    half();
    scl_rel();
    half();
    sda_rel();
    half();
}
static void wbit(int b) {
    if (b)
        sda_rel();
    else
        sda_low();
    half();
    scl_rel();
    half();
    scl_low();
    half();
}
static int rbit(void) {
    sda_rel();
    half();
    scl_rel();
    half();
    int v = sda_val();
    scl_low();
    half();
    return v;
}
static int wbyte(uint8_t v) {
    for (int i = 7; i >= 0; i--)
        wbit((v >> i) & 1);
    return rbit(); /* 0 = ACK */
}

static uint8_t g_addr;

int i2c_bb_init(uint8_t addr7) {
    wr(MUX_B20, (rd(MUX_B20) & ~0x7u) | FUNC_GPIO);
    wr(MUX_B21, (rd(MUX_B21) & ~0x7u) | FUNC_GPIO);
    sda_rel();
    scl_rel();
    g_addr = addr7;
    return 0;
}

int i2c_bb_write(const uint8_t *buf, size_t n) {
    start();
    if (wbyte((uint8_t)(g_addr << 1)) != 0) {
        stop();
        return -1;
    }
    int rc = 0;
    for (size_t i = 0; i < n; i++)
        if (wbyte(buf[i]) != 0)
            rc = -1;
    stop();
    return rc;
}
