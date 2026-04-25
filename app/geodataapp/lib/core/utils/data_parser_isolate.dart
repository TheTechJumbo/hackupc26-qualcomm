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

/// The isolate entry point function
/// MUST be a top-level function or static method to be used with compute()
Map<String, dynamic>? parseBlePayload(ParsingTask task) {
  try {
    // Example format: Tag:Trash|Conf:0.85
    final raw = task.rawBleData;
    
    // Simple parsing logic
    final parts = raw.split('|');
    if (parts.length != 2) return null;

    final tagPart = parts[0].split(':');
    final confPart = parts[1].split(':');

    if (tagPart.length != 2 || confPart.length != 2) return null;

    final tag = tagPart[1];
    final confidence = double.tryParse(confPart[1]) ?? 0.0;

    // Construct the payload to send to Firestore
    return {
      'lat': task.latitude,
      'lng': task.longitude,
      'tag': tag,
      'confidence': confidence,
      'timestamp': DateTime.now().toIso8601String(), // We will override this with FieldValue.serverTimestamp() before uploading
    };
  } catch (e) {
    // If parsing fails, return null
    return null;
  }
}
