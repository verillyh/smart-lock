#include <Servo.h>
#include <TimerOne.h>

#define servoPin 9
#define motionSensorPin 2
#define microphonePin A5
#define lockAngle 30
#define unlockAngle 180

unsigned long lastMicros = 0;
const unsigned long interval = 125;
unsigned long lastMotionTime = 0;
const unsigned long motionCooldown = 12000;
unsigned long unlockTime = 0;
bool unlocking = false;

bool motionDetected = false;
bool recordAudio = false;

Servo servo;

void setup() {
  // Set motion sensor
  pinMode(motionSensorPin, INPUT);
  attachInterrupt(digitalPinToInterrupt(motionSensorPin), motionDetectedFunc, RISING);
  // Set serial
  Serial.begin(230400);
  // Set servo
  servo.attach(servoPin);
  servo.write(lockAngle);
}

void loop() {
  // Unlock for only 3 seconds, then lock again
  if (unlocking && millis() - unlockTime >= 3000) {
    lock();
    unlocking = false;
  }

  // Send audio 
  if (recordAudio) {
    if (micros() - lastMicros >= interval) {
      lastMicros += interval;
      
      int val = analogRead(microphonePin);
      Serial.write(lowByte(val));
      Serial.write(highByte(val));
    }
  }

  // Handle serial inputs
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    if (input == "unlock") {
      unlock();
    } 
    else if (input == "lock") {
      lock();
    }
    else if (input == "Audio START") {
      recordAudio = true;
      Serial.write("<SMART_LOCK_AUDIO>");
    }
    else if (input == "Audio STOP") {
      recordAudio = false;
    }
  }

  // Send signal to RPi when motion detected
  if (motionDetected) {
    Serial.write("<SMART_LOCK_MOTION>");
    motionDetected = false;
  }
}

void unlock() {
  servo.write(unlockAngle);
  unlockTime = millis();
  unlocking = true;
}

void motionDetectedFunc() {
  unsigned long currentMillis = millis();
  if (currentMillis - lastMotionTime >= motionCooldown) {
    motionDetected = true;
    lastMotionTime = currentMillis;
  }
}

void lock() {
  servo.write(lockAngle);
}
