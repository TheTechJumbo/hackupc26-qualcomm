import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:flutter_background/flutter_background.dart';

class BleService {
  // Check if Bluetooth is available and turned on
  static Future<bool> isBluetoothEnabled() async {
    final state = await FlutterBluePlus.adapterState.first;
    return state == BluetoothAdapterState.on;
  }

  // Configuration for the Android foreground notification
  static const androidConfig = FlutterBackgroundAndroidConfig(
    notificationTitle: 'Edge AI Companion',
    notificationText: 'Scanning for Edge AI nodes...',
    notificationImportance: AndroidNotificationImportance.normal,
    notificationIcon: AndroidResource(name: 'ic_launcher', defType: 'mipmap'),
  );

  /// Enable background execution so BLE + GPS keep working when minimized
  static Future<bool> _enableBackground() async {
    try {
      bool hasPermissions = await FlutterBackground.hasPermissions;
      if (!hasPermissions) {
        hasPermissions = await FlutterBackground.initialize(androidConfig: androidConfig);
      }
      if (hasPermissions && !FlutterBackground.isBackgroundExecutionEnabled) {
        await FlutterBackground.enableBackgroundExecution();
        debugPrint('Background: Execution enabled');
      }
      return true;
    } catch (e) {
      debugPrint('Background: Failed to enable — $e');
      return false;
    }
  }

  /// Disable background execution (removes the persistent notification)
  static Future<void> _disableBackground() async {
    try {
      if (FlutterBackground.isBackgroundExecutionEnabled) {
        await FlutterBackground.disableBackgroundExecution();
        debugPrint('Background: Execution disabled');
      }
    } catch (e) {
      debugPrint('Background: Failed to disable — $e');
    }
  }

  // Start scanning — also starts background execution
  static Future<void> startScan({required String serviceUuid}) async {
    await _enableBackground();
    // No timeout — scan runs until stopScan() is called explicitly
    await FlutterBluePlus.startScan(
      withServices: [Guid(serviceUuid)],
    );
  }

  // Stop scanning — also stops background execution
  static Future<void> stopScan() async {
    await FlutterBluePlus.stopScan();
    await _disableBackground();
  }

  // Stop background execution only (called on disconnect)
  static Future<void> disableBackground() async {
    await _disableBackground();
  }
}
