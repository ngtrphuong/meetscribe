import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _serverController = TextEditingController(text: 'http://192.168.1.100:9876');

  @override
  void initState() {
    super.initState();
    final box = Hive.box('settings');
    _serverController.text = box.get('server_url', defaultValue: 'http://192.168.1.100:9876') as String;
  }

  void _save() {
    final box = Hive.box('settings');
    box.put('server_url', _serverController.text.trim());
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Đã lưu cài đặt')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Cài đặt')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('URL Server', style: TextStyle(color: Colors.grey, fontSize: 13)),
            const SizedBox(height: 8),
            TextField(
              controller: _serverController,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                hintText: 'http://192.168.1.100:9876',
                hintStyle: TextStyle(color: Colors.grey),
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _save,
                child: const Text('Lưu'),
              ),
            ),
            const SizedBox(height: 32),
            const Divider(color: Colors.grey),
            const SizedBox(height: 16),
            const Text(
              'Tuân thủ Nghị định 356/2025',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text(
              'Dữ liệu sinh trắc học (voiceprint) được mã hoá và chỉ lưu trên máy chủ cục bộ. '
              'Bạn có thể xoá voiceprint bất kỳ lúc nào qua Cài đặt → Tuân thủ.',
              style: TextStyle(color: Colors.grey, fontSize: 13, height: 1.5),
            ),
          ],
        ),
      ),
    );
  }
}
