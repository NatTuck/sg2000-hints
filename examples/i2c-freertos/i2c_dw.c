/* i2c_dw.c - DesignWare I2C3 master driver for the SG2000 little C906 core.
 *
 * REASONED, not board-tested. The little core runs in M-mode with no MMU, so
 * `*(volatile uint32_t *)addr` is a physical access: there is no /dev/mem and
 * no mmap here. This is the same controller the Linux i2c-dev rung talks to
 * (base 0x04030000), reprogrammed from scratch.
 *
 * Before the controller will respond, the little core must:
 *   1. route the pads to IIC3        (pad mux regs 0x03001158 / 0x0300115c)
 *   2. ungate the I2C3 clock         (CCU/RST block: board-specific - see note)
 * On Linux the kernel driver does (2) for us; that is exactly why a userspace
 * mmap of 0x04030000 reads back 0 until the block is unbound and re-clocked.
 */
#include "i2c_dw.h"

/* --- SG2000 addresses ----------------------------------------------------- */
#define I2C3_BASE 0x04030000UL
#define MUX_B20 0x03001158UL /* XGPIOB[20] pad function (header pin 3, SDA) */
#define MUX_B21 0x0300115CUL /* XGPIOB[21] pad function (header pin 5, SCL) */
#define FUNC_IIC3_SDA 5u
#define FUNC_IIC3_SCL 5u

/* DesignWare I2C register offsets. */
#define IC_CON 0x00
#define IC_TAR 0x04
#define IC_DATA_CMD 0x10
#define IC_INTR_MASK 0x30
#define IC_CLR_TX_ABRT 0x54
#define IC_ENABLE 0x6C
#define IC_STATUS 0x70
#define IC_TX_ABRT_SOURCE 0x80
#define IC_ENABLE_STATUS 0x9C

#define ST_TFNF (1u << 1)
#define ST_MST_ACT (1u << 5)
#define DC_STOP (1u << 9)
#define SPIN_LIMIT 2000000L

static inline uint32_t mmio_rd(uint32_t a) { return *(volatile uint32_t *)a; }
static inline void mmio_wr(uint32_t a, uint32_t v) {
    *(volatile uint32_t *)a = v;
}
#define RD(off) mmio_rd(I2C3_BASE + (off))
#define WR(off, v) mmio_wr(I2C3_BASE + (off), (v))

extern void i2c_clock_enable(void); /* vendor CCU/RST call - platform specific */

static int wait_mask(uint32_t off, uint32_t mask, int want_set) {
    for (long i = 0; i < SPIN_LIMIT; i++)
        if (!!(RD(off) & mask) == want_set)
            return 0;
    return -1; /* timeout: clock gated or bus held */
}

int i2c_dw_init(uint8_t addr7) {
    /* 1. pads -> IIC3 (clear bits [2:0], select function). */
    mmio_wr(MUX_B20, (mmio_rd(MUX_B20) & ~0x7u) | FUNC_IIC3_SDA);
    mmio_wr(MUX_B21, (mmio_rd(MUX_B21) & ~0x7u) | FUNC_IIC3_SCL);

    /* 2. ungate the controller clock (vendor BSP). */
    i2c_clock_enable();

    /* 3. controller: master, standard speed, restart-enable, no slave. */
    WR(IC_ENABLE, 0);
    (void)wait_mask(IC_ENABLE_STATUS, 1, 0);
    WR(IC_INTR_MASK, 0);
    WR(IC_CON, (1u << 0) | (1u << 1) | (1u << 5) | (1u << 6));
    WR(IC_TAR, addr7 & 0x3FF);
    WR(IC_ENABLE, 1);
    return 0;
}

int i2c_dw_write(const uint8_t *buf, size_t n) {
    for (size_t i = 0; i < n; i++) {
        if (wait_mask(IC_STATUS, ST_TFNF, 1))
            return -1;
        uint32_t v = buf[i];
        if (i == n - 1)
            v |= DC_STOP;
        WR(IC_DATA_CMD, v);
    }
    if (wait_mask(IC_STATUS, ST_MST_ACT, 0))
        return -1;
    if (RD(IC_TX_ABRT_SOURCE)) {
        (void)RD(IC_CLR_TX_ABRT);
        return -1;
    }
    return 0;
}
