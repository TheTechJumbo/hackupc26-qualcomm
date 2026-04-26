import 'dart:convert';

/// Data passed to the isolate
class ParsingTask {
  final String rawBleData;
  final double latitude;
  final double longitude;

  ParsingTask({
    required this.rawBleData,
    required this.latitude,
    required this.longitude,
  });
}

/// The isolate entry point function.
/// MUST be a top-level function or static method to be used with compute().
///
/// The Arduino sends a JSON object like:
///   {"humidity_percent": 42.5, "temperature_c": 27.5, "timestamp": "...", "toxicity_level": "medium", "trash_detected": true}
///
/// This function decodes it, merges in the phone's GPS coordinates, and
/// returns a flat Map that the DatabaseService can insert directly.
Map<String, dynamic>? parseBlePayload(ParsingTask task) {
  try {
    final raw = task.rawBleData.trim();
    print('ISOLATE: Parsing raw payload: $raw');

    // Decode the JSON string from the Arduino
    final decoded = jsonDecode(raw);

    // REASON: The Arduino sends a JSON *object* (Map), not an array.
    // We must check the type and handle it as a Map.
    if (decoded is! Map<String, dynamic>) {
      print('ISOLATE Error: Expected a JSON object but got ${decoded.runtimeType}');
      return null;
    }

    // Merge the phone's GPS coordinates into the Arduino's payload.
    // REASON: The Arduino does not have GPS — the phone provides lat/lng.
    final payload = <String, dynamic>{
      ...decoded,               // spread all Arduino fields with their original keys
      'latitude': task.latitude,
      'longitude': task.longitude,
    };

    print('ISOLATE: Successfully built payload: $payload');
    return payload;
  } catch (e) {
    print('ISOLATE Error: Failed to parse payload: $e');
    return null;
  }
}
