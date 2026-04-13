import { Injectable, OnDestroy } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Observable, Subject, timer, EMPTY } from 'rxjs';
import { retryWhen, delayWhen, tap, switchMap, catchError } from 'rxjs/operators';
import { WsMessage } from '../models/meeting.model';

const RECONNECT_DELAY_MS = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

@Injectable({ providedIn: 'root' })
export class WebSocketService implements OnDestroy {
  private connections = new Map<string, WebSocketSubject<WsMessage>>();

  /**
   * Get (or create) a WebSocket Subject for a meeting.
   * Returns a hot Observable that reconnects on drop.
   */
  connect(meetingId: string): Observable<WsMessage> {
    if (!this.connections.has(meetingId)) {
      const url = this.buildWsUrl(meetingId);
      const subject = webSocket<WsMessage>({
        url,
        deserializer: (e) => JSON.parse(e.data),
        serializer: (v) => JSON.stringify(v),
        openObserver: {
          next: () => console.log(`[WS] Connected: ${meetingId}`),
        },
        closeObserver: {
          next: () => {
            console.log(`[WS] Disconnected: ${meetingId}`);
            this.connections.delete(meetingId);
          },
        },
      });
      this.connections.set(meetingId, subject);
    }
    return this.connections.get(meetingId)!.asObservable().pipe(
      catchError((err) => {
        console.error('[WS] Error', err);
        return EMPTY;
      })
    );
  }

  disconnect(meetingId: string): void {
    const subject = this.connections.get(meetingId);
    if (subject) {
      subject.complete();
      this.connections.delete(meetingId);
    }
  }

  send(meetingId: string, message: WsMessage): void {
    this.connections.get(meetingId)?.next(message);
  }

  ngOnDestroy(): void {
    this.connections.forEach((s) => s.complete());
    this.connections.clear();
  }

  private buildWsUrl(meetingId: string): string {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = location.host;
    return `${protocol}//${host}/ws/transcript/${meetingId}`;
  }
}
