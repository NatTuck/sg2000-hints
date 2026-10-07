/* oled-bitbang.ino - drive the SSD1306 from the little C906 core with no OS,
 * no Wire library, and no DesignWare controller: bit-bang I2C on the header
 * pads and reuse the same transport-agnostic ssd1306.h as the Linux examples.
 *
 * VERIFIED on the Oz64 via remoteproc. Header pin 3 = XGPIOB[20] = SDA,
 * pin 5 = XGPIOB[21] = SCL. The little core runs in M-mode, so the register
 * addresses below are physical: no /dev/mem, no mmap.
 *
 * Build: arduino-cli compile --fqbn sophgo:SG200X:duos --build-path build oled-bitbang
 */
#include <string.h>

#include "ssd1306.h"

#define MUX_B20 0x03001158UL /* XGPIOB[20] pad function (header pin 3) */
#define MUX_B21 0x0300115CUL /* XGPIOB[21] pad function (header pin 5) */
#define GPIOB_BASE 0x03021000UL
#define SDA 20
#define SCL 21
#define FUNC_GPIO 3u

#define DR (GPIOB_BASE + 0x00)
#define DDR (GPIOB_BASE + 0x04)
#define EXT (GPIOB_BASE + 0x50)

static inline uint32_t r32(uint32_t a) { return *(volatile uint32_t *)a; }
static inline void w32(uint32_t a, uint32_t v) { *(volatile uint32_t *)a = v; }

/* open-drain emulation: drive low as output, release (high-Z) for high */
static void pad_out(int bit, int high) {
    uint32_t d = r32(DR);
    if (high)
        d |= (1u << bit);
    else
        d &= ~(1u << bit);
    w32(DR, d);
    w32(DDR, r32(DDR) | (1u << bit));
}
static void pad_rel(int bit) { w32(DDR, r32(DDR) & ~(1u << bit)); }
static void sda_low(void) { pad_out(SDA, 0); }
static void sda_rel(void) { pad_rel(SDA); }
static void scl_low(void) { pad_out(SCL, 0); }
static void scl_rel(void) { pad_rel(SCL); }
static int sda_val(void) {
    pad_rel(SDA);
    return (int)((r32(EXT) >> SDA) & 1u);
}

static void half(void) { delayMicroseconds(5); } /* ~100 kHz */

static void i2c_start(void) {
    sda_rel();
    scl_rel();
    half();
    sda_low();
    half();
    scl_low();
    half();
}
static void i2c_stop(void) {
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

static int wbuf(const uint8_t *b, size_t n) {
    i2c_start();
    if (wbyte((uint8_t)(OLED_ADDR << 1)) != 0) {
        i2c_stop();
        return -1;
    }
    for (size_t i = 0; i < n; i++)
        (void)wbyte(b[i]);
    i2c_stop();
    return 0;
}

/* transport callback expected by ssd1306.h */
static void oled_cb(void *ctx, const uint8_t *buf, size_t len, int is_data) {
    (void)ctx;
    uint8_t tmp[1 + 64];
    for (size_t off = 0; off < len; off += 64) {
        size_t n = len - off;
        if (n > 64)
            n = 64;
        tmp[0] = is_data ? 0x40 : 0x00;
        memcpy(tmp + 1, buf + off, n);
        (void)wbuf(tmp, n + 1);
    }
}

static oled_t o;

void setup() {
    w32(MUX_B20, (r32(MUX_B20) & ~0x7u) | FUNC_GPIO);
    w32(MUX_B21, (r32(MUX_B21) & ~0x7u) | FUNC_GPIO);
    sda_rel();
    scl_rel();

    oled_init(&o, oled_cb, NULL);
    oled_text(&o, 0, 0, "OZ64");
    oled_text(&o, 0, 12, "I2C bit-bang");
    oled_text(&o, 0, 24, "SSD1306 0x3C");
    oled_flush(&o);
}

void loop() {
    delay(1000);
}
