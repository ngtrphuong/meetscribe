/// Recording screen — streams audio to backend WebSocket.
/// Android: ForegroundService with FOREGROUND_SERVICE_TYPE_MICROPHONE
/// iOS: AVAudioSession(category: .playAndRecord) + UIBackgroundModes: audio
import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../../../core/services/api_service.dart';

class RecordingScreen extends ConsumerStatefulWidget {
  const RecordingScreen({super.key});

  @override
  ConsumerState<RecordingScreen> createState() => _RecordingScreenState();
}

class _RecordingScreenState extends ConsumerState<RecordingScreen> {
  final _recorder = AudioRecorder();
  WebSocketChannel? _wsChannel;
  String? _meetingId;
  bool _isRecording = false;
  bool _isPaused = false;
  String _status = 'idle';
  StreamSubscription? _streamSub;

  @override
  void dispose() {
    _stopAll();
    super.dispose();
  }

  Future<void> _start() async {
    // Request mic permission (Decree 356 — must be first)
    final status = await Permission.microphone.request();
    if (!status.isGranted) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Cần quyền truy cập microphone')),
        );
      }
      return;
    }

    final api = ref.read(apiServiceProvider);

    // Start meeting on backend
    final result = await api.startRecording(language: 'vi');
    final meetingId = result['meeting_id'] as String;
    setState(() { _meetingId = meetingId; });

    // Open WebSocket for receiving transcript
    _wsChannel = WebSocketChannel.connect(Uri.parse(api.wsUrl(meetingId)));
    _wsChannel!.stream.listen(
      (msg) { /* Handle transcript messages — update UI */ },
      onDone: () {},
    );

    // Start PCM recording and stream via WebSocket
    if (await _recorder.hasPermission()) {
      final stream = await _recorder.startStream(const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      ));

      _streamSub = stream.listen((chunk) {
        if (_wsChannel != null && !_isPaused) {
          _wsChannel!.sink.add(Uint8List.fromList(chunk));
        }
      });
    }

    setState(() { _isRecording = true; _status = 'recording'; });
  }

  Future<void> _stop() async {
    await _recorder.stop();
    _streamSub?.cancel();

    if (_meetingId != null) {
      await ref.read(apiServiceProvider).stopRecording(_meetingId!);
      _wsChannel?.sink.close();
      if (mounted) context.go('/meetings/$_meetingId');
    }
  }

  void _stopAll() {
    _recorder.cancel();
    _streamSub?.cancel();
    _wsChannel?.sink.close();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ghi âm cuộc họp')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Status indicator
            AnimatedContainer(
              duration: const Duration(milliseconds: 300),
              width: 120,
              height: 120,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isRecording
                    ? Colors.red.withOpacity(0.15)
                    : Colors.grey.withOpacity(0.1),
                border: Border.all(
                  color: _isRecording ? Colors.red : Colors.grey,
                  width: 2,
                ),
              ),
              child: Icon(
                _isRecording ? Icons.mic : Icons.mic_off,
                size: 48,
                color: _isRecording ? Colors.red : Colors.grey,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              _isRecording ? 'Đang ghi âm…' : 'Sẵn sàng ghi âm',
              style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 48),

            if (!_isRecording)
              ElevatedButton.icon(
                onPressed: _start,
                icon: const Icon(Icons.fiber_manual_record),
                label: const Text('Bắt đầu'),
              )
            else
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  OutlinedButton(
                    onPressed: () => setState(() => _isPaused = !_isPaused),
                    child: Text(_isPaused ? 'Tiếp tục' : 'Tạm dừng'),
                  ),
                  const SizedBox(width: 16),
                  ElevatedButton(
                    onPressed: _stop,
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
                    child: const Text('Dừng & Xử lý'),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
