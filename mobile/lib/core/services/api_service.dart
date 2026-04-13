import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'api_service.g.dart';

@riverpod
ApiService apiService(ApiServiceRef ref) => ApiService();

class ApiService {
  static const _defaultBaseUrl = 'http://192.168.1.100:9876';

  late final Dio _dio;

  ApiService({String? baseUrl}) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl ?? _defaultBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      headers: {'Content-Type': 'application/json'},
    ));
  }

  Future<Map<String, dynamic>> startRecording({
    String? title,
    String language = 'vi',
    bool consentRecording = false,
    bool consentVoiceprint = false,
    String templateName = 'general_vi',
  }) async {
    final resp = await _dio.post('/api/recording/start', data: {
      'title': title,
      'language': language,
      'consent_recording': consentRecording,
      'consent_voiceprint': consentVoiceprint,
      'template_name': templateName,
    });
    return resp.data as Map<String, dynamic>;
  }

  Future<void> stopRecording(String meetingId) async {
    await _dio.post('/api/recording/stop', data: {'meeting_id': meetingId});
  }

  Future<List<dynamic>> listMeetings({int page = 1, int perPage = 20}) async {
    final resp = await _dio.get('/api/meetings', queryParameters: {
      'page': page,
      'per_page': perPage,
    });
    return (resp.data as Map<String, dynamic>)['meetings'] as List;
  }

  Future<Map<String, dynamic>> getMeeting(String id) async {
    final resp = await _dio.get('/api/meetings/$id');
    return resp.data as Map<String, dynamic>;
  }

  Future<List<dynamic>> getTranscript(String id) async {
    final resp = await _dio.get('/api/meetings/$id/transcript');
    return (resp.data as Map<String, dynamic>)['segments'] as List;
  }

  String wsUrl(String meetingId) {
    final base = _dio.options.baseUrl
        .replaceFirst('http://', 'ws://')
        .replaceFirst('https://', 'wss://');
    return '$base/ws/transcript/$meetingId';
  }
}
