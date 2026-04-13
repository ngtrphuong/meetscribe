/**
 * MeetScribe Electron main process.
 *
 * Responsibilities:
 * - Create BrowserWindow loading Angular build or dev server
 * - System tray (green=idle, red=recording, blue=processing)
 * - Global hotkey: Ctrl+Shift+R → toggle recording
 * - macOS audio: enable loopback via commandLine switch
 * - Auto-updater via electron-updater
 * - Spawn Python backend as child process (optional)
 */

import {
  app, BrowserWindow, Tray, Menu, globalShortcut,
  ipcMain, shell, nativeImage,
} from 'electron';
import * as path from 'path';
import * as child_process from 'child_process';
import { autoUpdater } from 'electron-updater';

// ── macOS loopback audio (CLAUDE.md §10) ────────────────────────────────────
if (process.platform === 'darwin') {
  app.commandLine.appendSwitch('enable-features', 'MacLoopbackAudioForScreenShare');
}

const BACKEND_URL = 'http://localhost:9876';
const FRONTEND_URL = process.env['NODE_ENV'] === 'development'
  ? 'http://localhost:4200'
  : `file://${path.join(__dirname, '../frontend/dist/meetscribe-web/browser/index.html')}`;

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let backendProcess: child_process.ChildProcess | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    backgroundColor: '#030712',    // Tailwind gray-950
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadURL(FRONTEND_URL);

  mainWindow.once('ready-to-show', () => {
    mainWindow!.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

function createTray(): void {
  // Use a 16x16 icon (or nativeImage.createEmpty() for placeholder)
  const iconPath = path.join(__dirname, '../assets/tray-idle.png');
  const icon = nativeImage.createFromPath(iconPath).isEmpty()
    ? nativeImage.createEmpty()
    : nativeImage.createFromPath(iconPath);

  tray = new Tray(icon);
  tray.setToolTip('MeetScribe');

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Mở MeetScribe', click: () => mainWindow?.show() },
    { type: 'separator' },
    { label: 'Bắt đầu ghi âm (Ctrl+Shift+R)', click: () => triggerRecording() },
    { type: 'separator' },
    { label: 'Thoát', role: 'quit' },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => mainWindow?.show());
}

function triggerRecording(): void {
  mainWindow?.webContents.send('toggle-recording');
}

function startBackend(): void {
  // Try to start Python backend as child process
  const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
  const backendPath = path.join(__dirname, '../../backend');

  try {
    backendProcess = child_process.spawn(
      pythonCmd,
      ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '9876'],
      {
        cwd: path.join(__dirname, '../..'),
        stdio: 'pipe',
        env: { ...process.env },
      }
    );

    backendProcess.stdout?.on('data', (d) => console.log('[Backend]', d.toString()));
    backendProcess.stderr?.on('data', (d) => console.error('[Backend]', d.toString()));
    backendProcess.on('exit', (code) => console.log(`[Backend] exited with code ${code}`));

  } catch (e) {
    console.log('[Backend] Not auto-started — run separately');
  }
}

// ── App lifecycle ─────────────────────────────────────────────────────────────
app.whenReady().then(() => {
  // Start backend (optional — user can run it separately)
  if (process.env['MEETSCRIBE_START_BACKEND'] === '1') {
    startBackend();
  }

  createWindow();
  createTray();

  // Global hotkey: Ctrl+Shift+R → toggle recording
  globalShortcut.register('CommandOrControl+Shift+R', triggerRecording);

  // IPC: renderer → main
  ipcMain.handle('get-backend-url', () => BACKEND_URL);
  ipcMain.handle('open-external', (_, url: string) => shell.openExternal(url));

  // Update tray icon based on recording state
  ipcMain.on('recording-state', (_, state: string) => {
    if (!tray) return;
    const iconName = state === 'recording' ? 'tray-recording.png'
                   : state === 'processing' ? 'tray-processing.png'
                   : 'tray-idle.png';
    const iconPath = path.join(__dirname, '../assets', iconName);
    const icon = nativeImage.createFromPath(iconPath);
    if (!icon.isEmpty()) tray.setImage(icon);
  });

  // Auto-updater (production only)
  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.on('will-quit', () => {
  globalShortcut.unregisterAll();
  backendProcess?.kill();
});
