import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import '../core/constants/ble_constants.dart';

// Providers for general BLE states
final bluetoothStateProvider = StreamProvider<BluetoothAdapterState>((ref) {
  return FlutterBluePlus.adapterState;
});

final isScanningProvider = StreamProvider<bool>((ref) {
  return FlutterBluePlus.isScanning;
});

// A provider that tries to find and connect to the Edge Node device.
// Returns the connected BluetoothDevice if successful.
final edgeNodeDeviceProvider = StreamProvider<BluetoothDevice?>((ref) async* {
  // Listen to scan results
  StreamSubscription? subscription;
  BluetoothDevice? connectedDevice;

  void connectToDevice(BluetoothDevice device) async {
    await device.connect(license: License.free, autoConnect: false);
    connectedDevice = device;
    await FlutterBluePlus.stopScan();
  }

  subscription = FlutterBluePlus.scanResults.listen((results) {
    for (ScanResult r in results) {
      if (r.advertisementData.serviceUuids.contains(Guid(BleConstants.edgeNodeServiceUuid))) {
        connectToDevice(r.device);
        break;
      }
    }
  });

  ref.onDispose(() {
    subscription?.cancel();
  });

  // We emit the currently connected device if any, or wait.
  // Actually, listening to FlutterBluePlus.connectedDevices might be better
  // to track connection states directly.
  
  yield* Stream.periodic(const Duration(seconds: 1), (_) {
    if (connectedDevice != null && !connectedDevice!.isConnected) {
      connectedDevice = null;
    }
    return connectedDevice;
  });
});
