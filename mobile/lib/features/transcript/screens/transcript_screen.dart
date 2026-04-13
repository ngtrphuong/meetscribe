import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../../core/services/api_service.dart';

class TranscriptScreen extends ConsumerStatefulWidget {
  const TranscriptScreen({super.key, required this.meetingId});
  final String meetingId;

  @override
  ConsumerState<TranscriptScreen> createState() => _TranscriptScreenState();
}

class _TranscriptScreenState extends ConsumerState<TranscriptScreen> {
  WebSocketChannel? _channel;
  final _segments = <Map<String, dynamic>>[];
  String _status = 'loading';

  @override
  void initState() {
    super.initState();
    _connect();
  }

  void _connect() {
    final api = ref.read(apiServiceProvider);
    _channel = WebSocketChannel.connect(Uri.parse(api.wsUrl(widget.meetingId)));
    _channel!.stream.listen(
      (msg) {
        final data = json.decode(msg as String) as Map<String, dynamic>;
        if (data['type'] == 'segment') {
          setState(() => _segments.add(data['data'] as Map<String, dynamic>));
        } else if (data['type'] == 'status') {
          setState(() => _status = (data['data'] as Map)['state'] as String? ?? 'idle');
        }
      },
      onDone: () => setState(() => _status = 'disconnected'),
    );
  }

  @override
  void dispose() {
    _channel?.sink.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Bản ghi'),
        actions: [
          if (_status == 'complete')
            TextButton(
              onPressed: () => context.go('/meetings/${widget.meetingId}/summary'),
              child: const Text('Tóm tắt →'),
            ),
        ],
      ),
      body: Column(
        children: [
          // Status bar
          Container(
            width: double.infinity,
            color: _statusColor(_status).withOpacity(0.1),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                Container(
                  width: 8, height: 8,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _statusColor(_status),
                  ),
                ),
                const SizedBox(width: 8),
                Text(_statusLabel(_status), style: TextStyle(color: _statusColor(_status))),
              ],
            ),
          ),
          // Segments
          Expanded(
            child: _segments.isEmpty
                ? const Center(child: Text('Chờ bản ghi…', style: TextStyle(color: Colors.grey)))
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _segments.length,
                    itemBuilder: (ctx, i) {
                      final seg = _segments[i];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            CircleAvatar(
                              radius: 16,
                              backgroundColor: Colors.indigo,
                              child: Text(
                                (seg['speaker_label'] ?? '?').toString()[0].toUpperCase(),
                                style: const TextStyle(color: Colors.white, fontSize: 12),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '${seg['speaker_name'] ?? seg['speaker_label'] ?? 'Unknown'}',
                                    style: const TextStyle(color: Colors.grey, fontSize: 12),
                                  ),
                                  Text(
                                    seg['text'] as String? ?? '',
                                    style: const TextStyle(color: Colors.white),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Color _statusColor(String s) => switch (s) {
    'recording' => Colors.red,
    'processing' => Colors.amber,
    'complete' => Colors.green,
    _ => Colors.grey,
  };

  String _statusLabel(String s) => switch (s) {
    'recording' => 'Đang ghi âm',
    'processing' => 'Đang xử lý',
    'complete' => 'Hoàn thành',
    _ => s,
  };
}
