#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>

ModulinoThermo thermo;
ModulinoLight light;

unsigned long lastSensorReadMs = 0;
const unsigned long SENSOR_INTERVAL_MS = 2000;

String get_state() {
  float temperature = thermo.getTemperature();
  float humidity = thermo.getHumidity();

  light.update();
  int lux = light.getLux();
  int ambientLight = light.getAL();
  int infrared = light.getIR();

  String json = "{";
  json += "\"temperature_c\":";
  json += String(temperature, 1);
  json += ",\"humidity_percent\":";
  json += String(humidity, 1);
  json += ",\"light_lux\":";
  json += String(lux);
  json += ",\"ambient_light\":";
  json += String(ambientLight);
  json += ",\"infrared\":";
  json += String(infrared);
  json += "}";

  return json;
}

void setup() {
  Bridge.begin();

  Modulino.begin();

  thermo.begin();
  light.begin();

  Bridge.provide("get_state", get_state);

  Monitor.println("Bike sensor sketch started with Thermo + Light");
}

void loop() {
  unsigned long now = millis();

  if (now - lastSensorReadMs >= SENSOR_INTERVAL_MS) {
    lastSensorReadMs = now;

    float temperature = thermo.getTemperature();
    float humidity = thermo.getHumidity();

    light.update();
    int lux = light.getLux();
    int ambientLight = light.getAL();
    int infrared = light.getIR();

    Monitor.print("Temperature: ");
    Monitor.print(String(temperature, 1));
    Monitor.print(" C, Humidity: ");
    Monitor.print(String(humidity, 1));
    Monitor.print(" %, Lux: ");
    Monitor.println(String(lux));

    Bridge.notify("sensor_reading", temperature, humidity, lux, ambientLight, infrared);
  }
}