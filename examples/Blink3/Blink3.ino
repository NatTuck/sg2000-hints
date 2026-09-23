#define LED_PIN 7

void setup() {
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_PIN, HIGH);
  delay(167);
  digitalWrite(LED_PIN, LOW);
  delay(167);
}
