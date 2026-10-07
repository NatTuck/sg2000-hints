/* oled_task.c - a FreeRTOS task that drives the SSD1306 every 500 ms.
 *
 * REASONED, not board-tested. Shows the shape: one task owns the I2C transport
 * and the display, built on the *same* transport-agnostic SSD1306 layer the
 * Linux examples use (../i2c-c/ssd1306.h). Pick the transport at compile time:
 *
 *   -DOLED_TRANSPORT_DW=1   DesignWare I2C3 registers (i2c_dw.c)
 *   -DOLED_TRANSPORT_DW=0   GPIO bit-bang              (i2c_bitbang.c)
 *
 * Pacing uses vTaskDelay(), so the task *blocks* instead of spinning; other
 * tasks (and a lower-priority idle task) run while the panel refreshes.
 */
#include "FreeRTOS.h"
#include "task.h"

#include <stdio.h>

#include "../i2c-c/ssd1306.h" /* shared OLED layer */
#include "i2c_bitbang.h"
#include "i2c_dw.h"

#ifndef OLED_TRANSPORT_DW
#define OLED_TRANSPORT_DW 1
#endif

/* --- transport adapter: prepend control byte, one transaction per chunk --- */
static int i2c_tx(const uint8_t *buf, size_t n) {
#if OLED_TRANSPORT_DW
    return i2c_dw_write(buf, n);
#else
    return i2c_bb_write(buf, n);
#endif
}

static void oled_write_cb(void *ctx, const uint8_t *buf, size_t len,
                          int is_data) {
    (void)ctx;
    uint8_t tmp[1 + 64];
    for (size_t off = 0; off < len; off += 64) {
        size_t n = len - off;
        if (n > 64)
            n = 64;
        tmp[0] = is_data ? 0x40 : 0x00;
        for (size_t i = 0; i < n; i++)
            tmp[1 + i] = buf[off + i];
        (void)i2c_tx(tmp, n + 1);
    }
}

static void oled_task(void *arg) {
    (void)arg;
    oled_t o;
    oled_init(&o, oled_write_cb, NULL);

    for (;;) {
        char line[24];
        oled_clear(&o);
        oled_text(&o, 0, 0, "Oz64 + FreeRTOS");
#if OLED_TRANSPORT_DW
        oled_text(&o, 0, 12, "I2C3 DesignWare");
#else
        oled_text(&o, 0, 12, "I2C3 bit-bang");
#endif
        snprintf(line, sizeof line, "tick %lu",
                 (unsigned long)xTaskGetTickCount());
        oled_text(&o, 0, 24, line);
        oled_flush(&o);

        vTaskDelay(pdMS_TO_TICKS(500)); /* block, do not busy-wait */
    }
}

/* Call once from main_cvirtos() before vTaskStartScheduler(). */
void oled_start(void) {
#if OLED_TRANSPORT_DW
    i2c_dw_init(OLED_ADDR);
#else
    i2c_bb_init(OLED_ADDR);
#endif
    xTaskCreate(oled_task, "oled", 1024, NULL, 2, NULL);
}
