# Urban Resilience - Mobile App Interface

## What is this?
This Flutter application is the mobile companion to the **Urban Resilience Edge Node** hardware project. 

While the physical Arduino sensor handles scanning the street environment for extreme microclimates and bio-hazards, this app acts as the essential bridge between the hardware and our cloud map.

## The Point of the App
This application exists to do three specific things in the background:
1. **Listen:** It connects to the Arduino via Bluetooth Low Energy (BLE) to receive live JSON data (Temperature, Humidity, and a calculated Bio-Decay Toxicity Score).
2. **Locate:** It grabs the user's exact GPS coordinates from the phone and attaches them to the incoming sensor data.
3. **Sync:** It securely pushes the complete, location-tagged payload up to our Supabase database so city operators can see a live map of urban hazards.

*Note: This repository contains only the Flutter mobile application. The C++ hardware sketches and cloud database configurations are managed as part of the broader project ecosystem.*
