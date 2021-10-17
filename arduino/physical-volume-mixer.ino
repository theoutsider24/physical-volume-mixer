#include <LiquidCrystal.h>
#include <SparkFun_TB6612.h>
#include <Encoder.h>
#include <Button.h>
#include <singleLEDLibrary.h>

#define ENABLE 11
#define DIRA 8
#define DIRB 9
#define STBY 10

#define DOWN 255
#define DOWNSLOW 50
#define UP -255
#define UPSLOW -50

const int PinCLK = 2; // Generating interrupts using CLK signal
const int PinDT = 3;  // Reading DT signal
const int PinSW = 12; // Reading Push Button switch

const int servoPin = 15;

const int offsetA = 1;

String application;

Motor motor1(DIRA, DIRB, ENABLE, offsetA, STBY);
Encoder myEnc(PinCLK, PinDT);

sllib touchSenseLED(6);

int lastPotVal = 0;
const int potPin = 8;
const int touchSensePin = 9;
int count = 0;

long oldPosition = 0;

int lastTouchSenseReading = 512;

boolean touched = false;
const int touchTickDelay = 5;
int touchTick = 0;

int target = 60;
int targetTemp = target;

Button calibrateButton(13);

boolean muteButtonDown = false;

boolean goDown = false;

LiquidCrystal lcd(30, 31, 32, 33, 34, 35);

int potMax = 1023;
int potMin = 0;

void calibrate()
{
  motor1.drive(255, 100);
  potMax = analogRead(potPin) - 1;
  motor1.drive(-255, 100);
  potMin = analogRead(potPin) + 1;
}

void setup()
{
  // initialize serial communication:
  Serial.begin(9600);
  // initialize the LED pin as an output:
  pinMode(13, INPUT);
  pinMode(touchSensePin, INPUT);
  lcd.begin(16, 2);

  pinMode(ENABLE, OUTPUT);
  pinMode(DIRA, OUTPUT);
  pinMode(DIRB, OUTPUT);
  pinMode(STBY, OUTPUT);

  pinMode(PinCLK, INPUT);
  pinMode(PinDT, INPUT);
  pinMode(PinSW, INPUT);
  digitalWrite(PinSW, HIGH);

  calibrateButton.begin();

  calibrate();

  Serial.println("INIT");
}
int rotaryEncoderChange = 0;

void loop()
{
  boolean newMuteButtonDown = !digitalRead(PinSW);

  if (!newMuteButtonDown && muteButtonDown)
  {
    Serial.println("MUTE");
  }
  muteButtonDown = newMuteButtonDown;

  if (calibrateButton.pressed())
    calibrate();

  long newPosition = myEnc.read();
  if (newPosition != oldPosition)
  {
    rotaryEncoderChange += (newPosition - oldPosition);
    oldPosition = newPosition;
  }
  if (abs(rotaryEncoderChange) >= 4)
  {
    int direction = rotaryEncoderChange / abs(rotaryEncoderChange);
    // Positive is clockwise
    if (direction > 0)
    {
      Serial.println("CLICK+");
    }
    else
    {
      Serial.println("CLICK-");
    }
    rotaryEncoderChange = 0;
  }

  // see if there's incoming serial data:
  if (Serial.available() > 0)
  {
    String message = Serial.readStringUntil('#');
    if (message.startsWith("VOL:"))
    {
      target = message.substring(4).toInt();
    }
    if (message.startsWith("APP:"))
    {
      application = message.substring(4);
    }
  }
  int digitalVal = digitalRead(13);

  lcd.setCursor(0, 0);
  lcd.print("                ");
  lcd.setCursor(0, 0);
  lcd.print(application);
  int potReading = map(analogRead(potPin), potMin, potMax, 0, 100);

  int touchSenseReading = analogRead(touchSensePin);

  int diff = abs(touchSenseReading - lastTouchSenseReading);

  if (touched)
  {
    touchTick--;
  }
  if (diff > 500)
  {
    // When a touch is detected, the effect should linger
    touched = true;
    touchTick = 20;
    touchSenseLED.setOnSingle();
  }
  if (touchTick == 0)
  {
    touched = false;
    touchSenseLED.setOffSingle();
  }
  lastTouchSenseReading = touchSenseReading;

  lcd.setCursor(0, 1);
  lcd.print("                ");
  lcd.setCursor(0, 1);
  lcd.print(touched);
  lcd.setCursor(2, 1);
  lcd.print(target);
  lcd.setCursor(5, 1);
  lcd.print(potReading);

  lcd.setCursor(8, 1);
  lcd.print(potReading);

  if (touched)
  {
    motor1.brake();
    if (abs(lastPotVal - potReading) >= 2 || (lastPotVal != potReading && (potReading == 100 || potReading == 0)))
    {
      Serial.println(potReading);
      target = potReading;
      lastPotVal = potReading;
    }
  }
  else
  {
    int minVal = 65;
    int maxSpeed = 220;

    int distance = abs(potReading - target);
    int speed = map(distance, 0, 100, minVal, maxSpeed);
    if (speed > 120)
    {
      speed = maxSpeed;
    }

    lcd.setCursor(8, 1);
    lcd.print(speed);

    if ((distance <= 2 && !(target == 0 || target == 100)) || distance == 0)
    {
      motor1.brake();
    }
    else if (potReading < target)
    {
      motor1.drive(speed);
    }
    else if (potReading > target)
    {
      motor1.drive(speed * -1);
    }
  }
}
