// BlinkMillis — two independent, non-blocking blinks.
// Status: reasoned from the working Blink/Blink4 sketches; NOT yet board-tested.
// Rung 2 of the four-rung ladder in freertos-slides/.
//
// LED_A = Arduino pin 7  (VIVO_D3    = XGPIOB_18, the J3 pin 7 LED)
// LED_B = Arduino pin 13 (VIVO_D9    = XGPIOB_12; add your own LED)
//
// The point: no delay() in loop(), so both rates coexist.

#define LED_A 7
#define LED_B 13

#define PERIOD_A_MS 500
#define PERIOD_B_MS 125

static uint32_t tA = 0;
static uint32_t tB = 0;

void setup() {
  pinMode(LED_A, OUTPUT);
  pinMode(LED_B, OUTPUT);
}

void loop() {
  uint32_t now = millis();

  if (now - tA >= PERIOD_A_MS) {
    tA = now;
    digitalWrite(LED_A, !digitalRead(LED_A));
  }

  if (now - tB >= PERIOD_B_MS) {
    tB = now;
    digitalWrite(LED_B, !digitalRead(LED_B));
  }
}
