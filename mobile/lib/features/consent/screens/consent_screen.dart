/// Consent screen — MUST appear before recording (Decree 356).
/// Two checkboxes: consent_recording + consent_voiceprint.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

class ConsentScreen extends ConsumerStatefulWidget {
  const ConsentScreen({super.key});

  @override
  ConsumerState<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends ConsumerState<ConsentScreen> {
  bool _consentRecording = false;
  bool _consentVoiceprint = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Xác nhận ghi âm')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Theo Nghị định 356/2025, bạn cần đồng ý trước khi bắt đầu ghi âm.',
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 32),

            _ConsentCheckbox(
              value: _consentRecording,
              title: 'Đồng ý ghi âm cuộc họp',
              subtitle: 'File WAV được lưu trên thiết bị cục bộ theo tuỳ chọn này.',
              onChanged: (v) => setState(() => _consentRecording = v ?? false),
            ),
            const SizedBox(height: 16),
            _ConsentCheckbox(
              value: _consentVoiceprint,
              title: 'Đồng ý nhận diện giọng nói (Voiceprint)',
              subtitle: 'Dữ liệu sinh trắc học lưu mã hoá, có thể xoá bất kỳ lúc nào.',
              onChanged: (v) => setState(() => _consentVoiceprint = v ?? false),
            ),

            const Spacer(),

            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => context.pop(),
                    child: const Text('Huỷ'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () => context.go('/record'),
                    child: const Text('Bắt đầu ghi âm'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ConsentCheckbox extends StatelessWidget {
  const _ConsentCheckbox({
    required this.value,
    required this.title,
    required this.subtitle,
    required this.onChanged,
  });

  final bool value;
  final String title;
  final String subtitle;
  final ValueChanged<bool?> onChanged;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => onChanged(!value),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Checkbox(value: value, onChanged: onChanged),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
                const SizedBox(height: 2),
                Text(subtitle, style: const TextStyle(color: Colors.grey, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
