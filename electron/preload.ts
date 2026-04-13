/**
 * Electron preload script — exposes safe IPC APIs to the renderer.
 * contextIsolation=true: only explicitly exposed functions are accessible.
 */

import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
  onToggleRecording: (cb: () => void) => {
    ipcRenderer.on('toggle-recording', cb);
    return () => ipcRenderer.removeListener('toggle-recording', cb);
  },
  sendRecordingState: (state: string) => {
    ipcRenderer.send('recording-state', state);
  },
});
