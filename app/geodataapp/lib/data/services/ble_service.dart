import 'package:flutter_blue_plus/flutter_blue_plus.dart';

class BleService {
  // Check if Bluetooth is available and turned on
  static Future<bool> isBluetoothEnabled() async {
    final state = await FlutterBluePlus.adapterState.first;
    return state == BluetoothAdapterState.on;
  }

  // Start scanning
  static Future<void> startScan({required String serviceUuid}) async {
    await FlutterBluePlus.startScan(
      withServices: [Guid(serviceUuid)],
      timeout: const Duration(seconds: 15),
    );
  }

  // Stop scanning
  static Future<void> stopScan() async {
    await FlutterBluePlus.stopScan();
  }
}
