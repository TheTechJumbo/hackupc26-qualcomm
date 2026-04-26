import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import '../core/constants/ble_constants.dart';
import '../core/utils/data_parser_isolate.dart';
import '../data/services/location_service.dart';
import '../data/services/database_service.dart';
import 'ble_state_provider.dart';

/// Provider to handle the orchestration of BLE Data -> GPS -> Isolate -> Firestore
final dataSyncProvider = Provider<DataSyncManager>((ref) {
  final manager = DataSyncManager();
  
  // Watch the connected device. If it changes or disconnects, we should update our listeners.
  ref.watch(edgeNodeDeviceProvider.future).then((device) {
    if (device != null) {
      manager.startListening(device);
    } else {
      manager.stopListening();
    }
  });

  return manager;
});

class DataSyncManager {
  StreamSubscription<List<int>>? _charSubscription;

  void startListening(BluetoothDevice device) async {
    // Discover services
    List<BluetoothService> services = await device.discoverServices();
    
    // Find the specific characteristic
    BluetoothCharacteristic? targetChar;
    for (var service in services) {
      if (service.uuid.toString().toUpperCase() == BleConstants.edgeNodeServiceUuid.toUpperCase()) {
        for (var char in service.characteristics) {
          if (char.uuid.toString().toUpperCase() == BleConstants.edgeNodeCharacteristicUuid.toUpperCase()) {
            targetChar = char;
            break;
          }
        }
      }
    }

    if (targetChar != null) {
      // Subscribe to notifications
      await targetChar.setNotifyValue(true);
      _charSubscription = targetChar.lastValueStream.listen((value) async {
        if (value.isNotEmpty) {
          final rawString = utf8.decode(value);
          await _processPayload(rawString);
        }
      });
    }
  }

  void stopListening() {
    _charSubscription?.cancel();
    _charSubscription = null;
  }

  Future<void> _processPayload(String rawString) async {
    // Print out the raw received string for testing
    debugPrint('--- RAW BLE PAYLOAD RECEIVED ---');
    debugPrint(rawString);
    debugPrint('--------------------------------');

    // 1. Fetch current GPS coordinates
    final position = await LocationService.getCurrentPosition();
    if (position == null) return; // Drop if location unavailable as per "Drop payload" logic when something fails

    // 2. Offload parsing to Isolate
    final task = ParsingTask(
      rawBleData: rawString,
      latitude: position.latitude,
      longitude: position.longitude,
    );
    
    final payloadMap = await compute(parseBlePayload, task);

    // 3. Push to Supabase
    if (payloadMap != null) {
      await DatabaseService.uploadEdgeData(payloadMap);
      
      // 4. Trigger Haptic feedback on success
      HapticFeedback.mediumImpact();
    }
  }
}
