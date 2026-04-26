import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import '../../core/constants/ble_constants.dart';
import '../../data/services/ble_service.dart';
import '../../providers/ble_state_provider.dart';
import '../../providers/data_sync_provider.dart';
import '../../data/services/database_service.dart';
import '../widgets/pulsing_indicator.dart';
import '../widgets/premium_empty_state.dart';
import 'dashboard_screen.dart';

class ConnectionScreen extends ConsumerWidget {
  const ConnectionScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final adapterState = ref.watch(bluetoothStateProvider);
    final isScanning = ref.watch(isScanningProvider);
    final connectedDevice = ref.watch(edgeNodeDeviceProvider);

    // Watch dataSyncProvider just to initialize it so it starts listening
    ref.watch(dataSyncProvider);

    return Scaffold(
      body: SafeArea(
        child: adapterState.when(
          data: (state) {
            if (state != BluetoothAdapterState.on) {
              return PremiumEmptyState(
                icon: Icons.bluetooth_disabled,
                title: 'Bluetooth Disabled',
                description: 'Please enable Bluetooth to connect to the Edge AI node.',
                actionText: 'Open Settings',
                onAction: () {
                  // Platform specific settings open could be implemented here
                },
              );
            }

            return connectedDevice.when(
              data: (device) {
                if (device != null) {
                  // Device connected
                  WidgetsBinding.instance.addPostFrameCallback((_) {
                    HapticFeedback.heavyImpact();
                    Navigator.of(context).pushReplacement(
                      PageRouteBuilder(
                        pageBuilder: (context, animation, secondaryAnimation) => const DashboardScreen(),
                        transitionsBuilder: (context, animation, secondaryAnimation, child) {
                          return FadeTransition(opacity: animation, child: child);
                        },
                        transitionDuration: const Duration(milliseconds: 800),
                      ),
                    );
                  });
                  return const Center(child: CircularProgressIndicator());
                } else {
                  // Not connected
                  final scanning = isScanning.value ?? false;
                  return _buildScanningUI(scanning);
                }
              },
              loading: () => _buildScanningUI(isScanning.value ?? false),
              error: (e, st) => Center(child: Text('Error: $e')),
            );
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, st) => Center(child: Text('Error: $e')),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final testPayload = {
            'latitude': 41.3851,
            'longitude': 2.1734,
            'detectedTag': "Trash",
            'confidence': "0.95",
          };
          
          await DatabaseService.uploadEdgeData(testPayload);
          
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Test Payload Fired! Check Supabase.', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                backgroundColor: Colors.green,
                behavior: SnackBarBehavior.floating,
              ),
            );
          }
        },
        backgroundColor: Colors.blueAccent,
        icon: const Icon(Icons.cloud_upload, color: Colors.white),
        label: const Text('Test Cloud', style: TextStyle(color: Colors.white)),
      ),
    );
  }

  Widget _buildScanningUI(bool scanning) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Hero(
            tag: 'node_icon',
            child: PulsingIndicator(isScanning: scanning),
          ),
          const SizedBox(height: 60),
          Text(
            scanning ? 'Searching for Edge Node...' : 'Ready to Connect',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w500, color: Colors.white),
          ),
          const SizedBox(height: 20),
          if (!scanning)
            ElevatedButton(
              onPressed: () {
                BleService.startScan(serviceUuid: BleConstants.edgeNodeServiceUuid);
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: Colors.black,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              ),
              child: const Text('Start Scan'),
            )
          else
            OutlinedButton(
              onPressed: () {
                BleService.stopScan();
              },
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Colors.white),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              ),
              child: const Text('Stop Scan'),
            )
        ],
      ),
    );
  }
}
