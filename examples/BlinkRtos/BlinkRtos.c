// BlinkRtos — two independent, prioritized, blocking blink tasks.
// Status: reasoned from the FreeRTOS RISC-V port and the Sophgo freertos/cvitek
// little-core port; NOT board-tested. Rung 4 of the four-rung ladder in
// freertos-slides/.
//
// The point: each task reads like the single-job Blink sketch. vTaskDelay()
// blocks and releases the CPU instead of spinning, and priority encodes
// importance. main_cvirtos() replaces setup()/loop() in the vendor port.
//
// pinMode()/digitalWrite() are shown for continuity with the Arduino rungs;
// a real vendor FreeRTOS image would use its GPIO driver instead.

#include <FreeRTOS.h>
#include <task.h>
#include <stdint.h>

typedef struct {
  uint8_t pin;
  TickType_t half;
} Blink;

static void blink_task(void *arg) {
  const Blink *b = (const Blink *)arg;
  pinMode(b->pin, OUTPUT);
  for (;;) {
    digitalWrite(b->pin, HIGH);
    vTaskDelay(b->half);
    digitalWrite(b->pin, LOW);
    vTaskDelay(b->half);
  }
}

void main_cvirtos(void) {
  static const Blink fast = { 7, pdMS_TO_TICKS(125) };
  static const Blink slow = { 13, pdMS_TO_TICKS(500) };

  xTaskCreate(blink_task, "fast", 256, (void *)&fast, 2, NULL);
  xTaskCreate(blink_task, "slow", 256, (void *)&slow, 1, NULL);

  vTaskStartScheduler();

  for (;;) {
  }
}
