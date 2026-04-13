import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/services/api_service.dart';

final meetingDetailProvider = FutureProvider.family<Map<String, dynamic>, String>(
  (ref, id) => ref.watch(apiServiceProvider).getMeeting(id),
);

class SummaryScreen extends ConsumerWidget {
  const SummaryScreen({super.key, required this.meetingId});
  final String meetingId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(meetingDetailProvider(meetingId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tóm tắt cuộc họp'),
        actions: [
          detail.maybeWhen(
            data: (d) => IconButton(
              icon: const Icon(Icons.copy),
              onPressed: () {
                final content = (d['summary'] as Map?)?['content'] as String? ?? '';
                Clipboard.setData(ClipboardData(text: content));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Đã sao chép vào clipboard')),
                );
              },
            ),
            orElse: () => const SizedBox.shrink(),
          ),
        ],
      ),
      body: detail.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Lỗi: $e')),
        data: (d) {
          final summary = (d['summary'] as Map?)?['content'] as String?;
          final actions = (d['action_items'] as List?) ?? [];

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // Meeting info card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(d['title'] as String? ?? '', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
                      const SizedBox(height: 4),
                      Text(d['started_at'] as String? ?? '', style: const TextStyle(color: Colors.grey, fontSize: 13)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Summary content
              if (summary != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: SelectableText(
                      summary,
                      style: const TextStyle(color: Colors.white, height: 1.6),
                    ),
                  ),
                )
              else
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('Chưa có tóm tắt', style: TextStyle(color: Colors.grey)),
                  ),
                ),

              // Action items
              if (actions.isNotEmpty) ...[
                const SizedBox(height: 12),
                const Text('Công việc cần làm', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                const SizedBox(height: 8),
                ...actions.map((item) {
                  final m = item as Map;
                  return Card(
                    child: ListTile(
                      title: Text(m['description'] as String? ?? '', style: const TextStyle(color: Colors.white)),
                      subtitle: Text('${m['owner'] ?? '—'} · ${m['deadline'] ?? '—'}', style: const TextStyle(color: Colors.grey)),
                      trailing: Text(m['status'] as String? ?? 'open', style: const TextStyle(color: Colors.indigo)),
                    ),
                  );
                }),
              ],
            ],
          );
        },
      ),
    );
  }
}
