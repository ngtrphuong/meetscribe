import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/services/api_service.dart';

final meetingsProvider = FutureProvider<List<dynamic>>((ref) async {
  return ref.watch(apiServiceProvider).listMeetings();
});

class MeetingListScreen extends ConsumerWidget {
  const MeetingListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final meetings = ref.watch(meetingsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cuộc họp'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => context.go('/settings'),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.go('/consent'),
        icon: const Icon(Icons.mic),
        label: const Text('Ghi âm mới'),
      ),
      body: meetings.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('Lỗi: $e', style: const TextStyle(color: Colors.red))),
        data: (list) {
          if (list.isEmpty) {
            return const Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('🎙️', style: TextStyle(fontSize: 48)),
                  SizedBox(height: 12),
                  Text('Chưa có cuộc họp nào', style: TextStyle(color: Colors.grey)),
                ],
              ),
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: list.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (ctx, i) {
              final m = list[i] as Map<String, dynamic>;
              return Card(
                child: ListTile(
                  title: Text(m['title'] as String? ?? 'Cuộc họp'),
                  subtitle: Text(m['started_at'] as String? ?? ''),
                  trailing: _StatusBadge(status: m['status'] as String? ?? ''),
                  onTap: () => context.go('/meetings/${m['id']}'),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'complete' => Colors.green,
      'recording' => Colors.red,
      'processing' => Colors.amber,
      _ => Colors.grey,
    };
    final label = switch (status) {
      'complete' => 'Xong',
      'recording' => 'Đang ghi',
      'processing' => 'Xử lý',
      _ => status,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label, style: TextStyle(color: color, fontSize: 11)),
    );
  }
}
