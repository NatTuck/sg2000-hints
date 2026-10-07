/* Drive the SSD1306 from Linux userspace by bit-banging I2C on two GPIO pads,
 * mapped straight out of /dev/mem. No i2c-dev, no kernel driver, no DesignWare
 * controller: just the two pad registers, open-drain style.
 *
 * This is the "raw register" rung of the Linux ladder and mirrors the GPIO
 * material in hints/gpio-software.md.
 *
 *   header pin 3 = XGPIOB[20] -> SDA
 *   header pin 5 = XGPIOB[21] -> SCL
 *
 * Build: riscv64-linux-gnu-gcc -static -O2 -o linux-mmap-bitbang \
 *            linux-mmap-bitbang.c
 * Run:   sudo ./linux-mmap-bitbang "Hello from bit-bang"
 */
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include "ssd1306.h"

#define MUX_BASE 0x03001000UL   /* pad function select */
#define GPIOB_BASE 0x03021000UL /* XGPIOB data/dir/input */
#define PAGE 0x1000UL

#define SDA_BIT 20 /* XGPIOB[20], header pin 3 */
#define SCL_BIT 21 /* XGPIOB[21], header pin 5 */

/* Pad mux registers (from `duo-pinmux -r B20/B21`). */
#define MUX_B20 (0x158 / 4)
#define MUX_B21 (0x15C / 4)
#define FUNC_GPIO 3u
#define FUNC_IIC3_SDA 5u
#define FUNC_IIC3_SCL 5u

static volatile uint32_t *mux;
static volatile uint32_t *g; /* GPIOB */
static int g_abort;

#define DR (g[0x00 / 4])
#define DDR (g[0x04 / 4])
#define EXT (g[0x50 / 4])

static void pad_out(int bit, int high) {
    if (high)
        DR |= (1u << bit);
    else
        DR &= ~(1u << bit);
    DDR |= (1u << bit); /* output */
}
static void pad_release(int bit) { DDR &= ~(1u << bit); } /* high-Z, pulled up */

static void sda_low(void) { pad_out(SDA_BIT, 0); }
static void sda_release(void) { pad_release(SDA_BIT); }
static void scl_low(void) { pad_out(SCL_BIT, 0); }
static void scl_release(void) { pad_release(SCL_BIT); }
static int sda_level(void) {
    pad_release(SDA_BIT);
    return (int)((EXT >> SDA_BIT) & 1u);
}

static void half(void) {
    struct timespec ts = {0, 5000}; /* 5 us -> ~100 kHz half period */
    nanosleep(&ts, NULL);
}

static void i2c_start(void) {
    sda_release();
    scl_release();
    half();
    sda_low();
    half();
    scl_low();
    half();
}
static void i2c_stop(void) {
    sda_low();
    half();
    scl_release();
    half();
    sda_release();
    half();
}
static int i2c_wbit(int b) {
    if (b)
        sda_release();
    else
        sda_low();
    half();
    scl_release();
    half();
    scl_low();
    half();
    return 0;
}
static int i2c_rbit(void) {
    sda_release();
    half();
    scl_release();
    half();
    int v = sda_level();
    scl_low();
    half();
    return v;
}
static int i2c_wbyte(uint8_t v) {
    for (int i = 7; i >= 0; i--)
        i2c_wbit((v >> i) & 1);
    return i2c_rbit(); /* 0 = ACK */
}

static void bb_tx(const uint8_t *buf, size_t n) {
    i2c_start();
    if (i2c_wbyte((uint8_t)(OLED_ADDR << 1)) != 0) {
        fprintf(stderr, "no ACK for address 0x%02X\n", OLED_ADDR);
        g_abort = 1;
        i2c_stop();
        return;
    }
    for (size_t i = 0; i < n; i++)
        if (i2c_wbyte(buf[i]) != 0)
            fprintf(stderr, "NACK at byte %zu\n", i);
    i2c_stop();
}

static void bb_cb(void *ctx, const uint8_t *buf, size_t len, int is_data) {
    (void)ctx;
    uint8_t tmp[1 + 64];
    for (size_t off = 0; off < len; off += 64) {
        size_t n = len - off;
        if (n > 64)
            n = 64;
        tmp[0] = is_data ? 0x40 : 0x00;
        for (size_t i = 0; i < n; i++)
            tmp[1 + i] = buf[off + i];
        bb_tx(tmp, n + 1);
        if (g_abort)
            return;
    }
}

int main(int argc, char **argv) {
    const char *text = argc > 1 ? argv[1] : "Hello from bit-bang";

    int fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (fd < 0) {
        perror("/dev/mem");
        return 1;
    }
    mux = mmap(NULL, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, MUX_BASE);
    g = mmap(NULL, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, GPIOB_BASE);
    if (mux == MAP_FAILED || g == MAP_FAILED) {
        perror("mmap");
        return 1;
    }

    /* Route B20/B21 to plain GPIO for bit-banging. */
    mux[MUX_B20] = (mux[MUX_B20] & ~0x7u) | FUNC_GPIO;
    mux[MUX_B21] = (mux[MUX_B21] & ~0x7u) | FUNC_GPIO;
    sda_release();
    scl_release();

    oled_t o;
    oled_init(&o, bb_cb, NULL);
    oled_draw_lines(&o, 0, 0, text);
    oled_flush(&o);

    /* Put the pads back on IIC3 so the kernel/i2c-3 keeps working. */
    mux[MUX_B20] = (mux[MUX_B20] & ~0x7u) | FUNC_IIC3_SDA;
    mux[MUX_B21] = (mux[MUX_B21] & ~0x7u) | FUNC_IIC3_SCL;

    if (g_abort)
        return 1;
    printf("wrote %s via GPIO bit-bang (B20=SDA, B21=SCL)\n", text);
    return 0;
}
