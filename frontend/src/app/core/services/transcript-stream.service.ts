/**
 * TranscriptStreamService — CLAUDE.md §8.2 mandatory pattern.
 *
 * WebSocket → RxJS (backpressure, filtering, batching)
 *           → Signal (zoneless DOM rendering)
 */
import { Injectable, OnDestroy, signal, computed } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Observable, Subject, Subscription } from 'rxjs';
import {
  filter, map, bufferTime, scan, distinctUntilChanged
} from 'rxjs/operators';

import { WebSocketService } from './websocket.service';
import { TranscriptSegment, AudioLevels, WsMessage } from '../models/meeting.model';

@Injectable({ providedIn: 'root' })
export class TranscriptStreamService implements OnDestroy {
  private sub?: Subscription;
  private currentMeetingId?: string;

  // ── Signals for DOM rendering ─────────────────────────────────────────────
  readonly segments = signal<TranscriptSegment[]>([]);
  readonly status = signal<string>('idle');
  readonly statusMessage = signal<string>('');
  readonly levels = signal<AudioLevels>({ system: 0, mic: 0 });
  readonly activeSpeaker = signal<string | undefined>(undefined);

  constructor(private ws: WebSocketService) {}

  /**
   * Start listening to a meeting's WebSocket stream.
   * Implements the CLAUDE.md §8.2 RxJS → Signal pattern.
   */
  listen(meetingId: string): void {
    if (this.currentMeetingId === meetingId) return;
    this.stop();

    this.currentMeetingId = meetingId;
    const stream$ = this.ws.connect(meetingId);

    // Segments: batch every 200ms, accumulate into array
    const segments$ = stream$.pipe(
      filter((msg) => msg.type === 'segment'),
      map((msg) => msg.data as TranscriptSegment),
      bufferTime(200),
      filter((batch) => batch.length > 0),
      scan(
        (acc, batch) => [...acc, ...batch],
        [] as TranscriptSegment[]
      )
    );

    // Status updates
    const status$ = stream$.pipe(
      filter((msg) => msg.type === 'status'),
      map((msg) => msg.data)
    );

    // Level meters (don't accumulate — latest value only)
    const level$ = stream$.pipe(
      filter((msg) => msg.type === 'level'),
      map((msg) => msg.data as AudioLevels)
    );

    // Diarization — track active speaker
    const diar$ = stream$.pipe(
      filter((msg) => msg.type === 'diarization'),
      map((msg) => msg.data?.speaker as string | undefined)
    );

    this.sub = new Subscription();

    this.sub.add(
      segments$.subscribe((segs) => this.segments.set(segs))
    );

    this.sub.add(
      status$.subscribe((s) => {
        this.status.set(s.state ?? 'idle');
        this.statusMessage.set(s.message ?? '');
      })
    );

    this.sub.add(
      level$.subscribe((l) => this.levels.set(l))
    );

    this.sub.add(
      diar$.subscribe((speaker) => this.activeSpeaker.set(speaker))
    );

    // Heartbeat — respond to server pings
    this.sub.add(
      stream$.pipe(filter((m) => m.type === 'ping')).subscribe(() => {
        this.ws.send(meetingId, { type: 'pong' });
      })
    );
  }

  stop(): void {
    this.sub?.unsubscribe();
    if (this.currentMeetingId) {
      this.ws.disconnect(this.currentMeetingId);
      this.currentMeetingId = undefined;
    }
    this.segments.set([]);
    this.levels.set({ system: 0, mic: 0 });
  }

  ngOnDestroy(): void {
    this.stop();
  }
}
