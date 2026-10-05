// BlinkTimerISR — blink driven by a periodic hardware timer interrupt.
// Status: illustrative / reasoned; NOT board-tested. The vendor core's timer
// setup API is not yet documented here, so timer_setup() is a placeholder.
// Rung 3 of the four-rung ladder in freertos-slides/.
//
// The point: the ISR gives an exact period decoupled from loop(), and it
// immediately introduces shared data (tick_a) between the ISR and loop().

#define LED_A 7

static volatile bool tick_a = false;

// In a real ISR you must re-arm the timer before returning.
extern "C" void timer_isr(void) {
  tick_a = true;
}

// Fill this in per the vendor core: point mtvec at the trap handler, program
// mtimecmp, and set mie.MTIE. On FreeRTOS this is what vPortSetupTimerInterrupt
// does for you. This stub exists only so the sketch links; replace it.
void timer_setup(uint32_t period_us, void (*handler)(void)) {
  (void)period_us;
  (void)handler;
}

void setup() {
  pinMode(LED_A, OUTPUT);
  timer_setup(1000, timer_isr);
}

void loop() {
  if (tick_a) {
    tick_a = false;
    digitalWrite(LED_A, !digitalRead(LED_A));
  }
}
