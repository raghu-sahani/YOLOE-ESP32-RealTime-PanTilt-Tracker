#include <ESP32Servo.h>
#include <stdio.h>
#include <string.h>

// Classic ESP32 DevKit/WROOM.
// Pan signal: GPIO18, tilt signal: GPIO19.
Servo panServo, tiltServo;

constexpr int PAN_PIN = 18;
constexpr int TILT_PIN = 19;
constexpr int MIN_US = 900;
constexpr int MAX_US = 2100;

int panUs = 1500;
int tiltUs = 1500;

char buffer[64];
size_t used = 0;
bool overflow = false;
unsigned long lastCommand = 0;

void acknowledge(unsigned long sequence) {
  Serial.print("ACK,");
  Serial.print(sequence);
  Serial.print(',');
  Serial.print(panUs);
  Serial.print(',');
  Serial.println(tiltUs);
}

void processCommand() {
  if (used == 0 || buffer[0] == '\0') return;

  char *hello = strstr(buffer, "HELLO");
  if (hello != nullptr && strcmp(hello, "HELLO") == 0) {
    Serial.println("PTSTUDIO,1");
    return;
  }

  if (strcmp(buffer, "H") == 0) {
    lastCommand = millis();
    return;
  }

  char *packet = strstr(buffer, "P,");
  if (packet == nullptr) return;

  unsigned long sequence;
  int p, t;
  char extra;
  int parsed = sscanf(packet, "P,%lu,%d,%d %c", &sequence, &p, &t, &extra);
  if (parsed != 3) {
    Serial.println("ERR,FORMAT");
    return;
  }

  if (p < MIN_US || p > MAX_US || t < MIN_US || t > MAX_US) {
    Serial.println("ERR,RANGE");
    return;
  }

  panUs = p;
  tiltUs = t;
  panServo.writeMicroseconds(panUs);
  tiltServo.writeMicroseconds(tiltUs);
  lastCommand = millis();
  acknowledge(sequence);
}

void setup() {
  Serial.begin(115200);
  delay(250);

  panServo.setPeriodHertz(50);
  tiltServo.setPeriodHertz(50);
  panServo.attach(PAN_PIN, MIN_US, MAX_US);
  tiltServo.attach(TILT_PIN, MIN_US, MAX_US);
  panServo.writeMicroseconds(panUs);
  tiltServo.writeMicroseconds(tiltUs);

  Serial.println("PTSTUDIO,1");
  lastCommand = millis();
}

void loop() {
  for (int count = 0; count < 128 && Serial.available(); ++count) {
    char c = (char)Serial.read();
    unsigned char uc = (unsigned char)c;

    if (c == '\r') continue;

    if (c == '\n') {
      if (!overflow) {
        buffer[used] = '\0';
        processCommand();
      } else {
        Serial.println("ERR,TOO_LONG");
      }
      used = 0;
      overflow = false;
      continue;
    }

    if (uc < 32 || uc > 126) {
      used = 0;
      overflow = false;
      continue;
    }

    if (!overflow) {
      if (used < sizeof(buffer) - 1) {
        buffer[used++] = c;
      } else {
        overflow = true;
      }
    }
  }
}
