class ScanPayload {
  final double lat;
  final double lng;
  final String tag;
  final double confidence;
  final DateTime timestamp;

  ScanPayload({
    required this.lat,
    required this.lng,
    required this.tag,
    required this.confidence,
    required this.timestamp,
  });

  Map<String, dynamic> toMap() {
    return {
      'lat': lat,
      'lng': lng,
      'tag': tag,
      'confidence': confidence,
      'timestamp': timestamp.toIso8601String(),
    };
  }
}
