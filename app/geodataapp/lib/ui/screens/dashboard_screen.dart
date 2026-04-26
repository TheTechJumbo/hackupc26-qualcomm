import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import '../../core/theme/app_theme.dart';
import '../../providers/ble_state_provider.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Keep watching the device to know if it disconnects
    final connectedDevice = ref.watch(edgeNodeDeviceProvider);
    
    // In a real scenario, we might also listen to the stream of parsed payloads
    // for local UI updates, but requirements state: 
    // "Do not cache the mapped route data heavily on the device; offload it to Firestore and clear local memory immediately."
    // So the dashboard simply shows active listening state.

    return Scaffold(
      appBar: AppBar(
        title: const Text('Session Active'),
        automaticallyImplyLeading: false, // Prevent back navigation unless intended
      ),
      body: SafeArea(
        child: connectedDevice.when(
          data: (device) {
            if (device == null) {
              // Disconnected, maybe show a modal or pop back
              WidgetsBinding.instance.addPostFrameCallback((_) {
                Navigator.of(context).pushReplacementNamed('/'); // Assumes / is ConnectionScreen in main.dart
              });
              return const SizedBox();
            }

            return _buildActiveSessionUI(device);
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, st) => Center(child: Text('Error: $e')),
        ),
      ),
    );
  }

  Widget _buildActiveSessionUI(BluetoothDevice device) {
    final deviceName = device.advName.isEmpty ? device.remoteId.str : device.advName;
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Hero(
            tag: 'node_icon',
            child: Container(
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppTheme.surfaceColor,
                border: Border.all(color: AppTheme.primaryColor, width: 2),
                boxShadow: [
                  BoxShadow(
                    color: AppTheme.primaryColor.withOpacity(0.3),
                    blurRadius: 20,
                    spreadRadius: 5,
                  )
                ]
              ),
              child: const Icon(Icons.satellite_alt, color: AppTheme.primaryColor, size: 40),
            ),
          ),
          const SizedBox(height: 40),
          Text(
            'Connected to $deviceName',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          const SizedBox(height: 16),
          const Text(
            'Listening to data stream...',
            style: TextStyle(color: AppTheme.textSecondaryColor, fontSize: 16),
          ),
          const SizedBox(height: 40),
          // A subtle indicator of background activity
          const CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryColor),
            strokeWidth: 2,
          ),
          const SizedBox(height: 60),
          OutlinedButton.icon(
            onPressed: () async {
              await device.disconnect();
            },
            icon: const Icon(Icons.link_off),
            label: const Text('Disconnect from Node'),
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.redAccent,
              side: const BorderSide(color: Colors.redAccent),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            ),
          ),
        ],
      ),
    );
  }
}
