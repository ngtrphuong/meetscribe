import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/meetings/screens/meeting_list_screen.dart';
import '../../features/recording/screens/recording_screen.dart';
import '../../features/transcript/screens/transcript_screen.dart';
import '../../features/summary/screens/summary_screen.dart';
import '../../features/settings/screens/settings_screen.dart';
import '../../features/consent/screens/consent_screen.dart';

part 'app_router.g.dart';

@riverpod
GoRouter appRouter(AppRouterRef ref) {
  return GoRouter(
    initialLocation: '/meetings',
    routes: [
      GoRoute(
        path: '/meetings',
        builder: (ctx, state) => const MeetingListScreen(),
      ),
      GoRoute(
        path: '/consent',
        builder: (ctx, state) => const ConsentScreen(),
      ),
      GoRoute(
        path: '/record',
        builder: (ctx, state) => const RecordingScreen(),
      ),
      GoRoute(
        path: '/meetings/:id',
        builder: (ctx, state) => TranscriptScreen(
          meetingId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/meetings/:id/summary',
        builder: (ctx, state) => SummaryScreen(
          meetingId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/settings',
        builder: (ctx, state) => const SettingsScreen(),
      ),
    ],
  );
}
