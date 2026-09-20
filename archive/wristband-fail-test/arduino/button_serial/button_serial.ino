// Arduino Uno R3: botão entre D2 e GND; o pull-up é interno.
const byte BUTTON_PIN = 2;
const unsigned long DEBOUNCE_MS = 35;

bool lastReading = HIGH;
bool stableState = HIGH;
unsigned long changedAt = 0;

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Serial.begin(115200);
}

void loop() {
  const bool reading = digitalRead(BUTTON_PIN);
  const unsigned long now = millis();

  if (reading != lastReading) {
    changedAt = now;
    lastReading = reading;
  }

  if (now - changedAt >= DEBOUNCE_MS && reading != stableState) {
    stableState = reading;
    if (stableState == LOW) {
      Serial.println("BUTTON");
    }
  }
}
