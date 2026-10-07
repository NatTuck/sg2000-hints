/* Drive the SSD1306 from Linux userspace through /dev/i2c-N.
 *
 * This is the "most abstract" rung: the kernel's i2c-dev exposes the
 * DesignWare controller as a character device, and one write() becomes one
 * I2C transaction. Address the chip with ioctl(I2C_SLAVE, 0x3C).
 *
 * Build (host, cross):
 *   riscv64-linux-gnu-gcc -static -O2 -o linux-i2c-dev linux-i2c-dev.c
 * Run (board):
 *   ./linux-i2c-dev /dev/i2c-3 "Hello Oz64"
 */
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include "ssd1306.h"

static int g_fd;
static const char *g_err;

/* One write() per chunk: [control byte][payload...]. 32-byte chunks keep the
 * transaction well inside the controller FIFO. */
static void i2c_write_cb(void *ctx, const uint8_t *buf, size_t len,
                         int is_data) {
    (void)ctx;
    uint8_t chunk[1 + 32];
    for (size_t off = 0; off < len; off += 32) {
        size_t n = len - off;
        if (n > 32)
            n = 32;
        chunk[0] = is_data ? 0x40 : 0x00;
        memcpy(chunk + 1, buf + off, n);
        if (write(g_fd, chunk, n + 1) != (ssize_t)(n + 1)) {
            g_err = "write";
            return;
        }
    }
}

int main(int argc, char **argv) {
    const char *path = argc > 1 ? argv[1] : "/dev/i2c-3";
    const char *text = argc > 2 ? argv[2] : "Hello Oz64";

    g_fd = open(path, O_RDWR);
    if (g_fd < 0) {
        perror(path);
        return 1;
    }
    if (ioctl(g_fd, I2C_SLAVE, OLED_ADDR) < 0) {
        perror("I2C_SLAVE");
        return 1;
    }

    oled_t o;
    oled_init(&o, i2c_write_cb, NULL);
    oled_draw_lines(&o, 0, 0, text);
    oled_flush(&o);

    if (g_err) {
        perror(g_err);
        return 1;
    }
    printf("wrote %s to %s @ 0x%02X (i2c-dev)\n", text, path, OLED_ADDR);
    close(g_fd);
    return 0;
}
