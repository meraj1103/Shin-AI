const { app, BrowserWindow, screen, ipcMain } = require('electron');
const path = require('path');

// ── Memory optimizations ─────────────────────────────────────────────────────
// Limit V8 heap to 64 MB (default is ~1.5 GB) — the orb UI uses very little JS
app.commandLine.appendSwitch('js-flags', '--max-old-space-size=64');
// Disable GPU compositing to save ~30-50 MB of VRAM/shared GPU memory
app.commandLine.appendSwitch('disable-gpu-compositing');
// Disable background throttling so the orb stays responsive even when unfocused
app.commandLine.appendSwitch('disable-renderer-backgrounding');

if (!app.requestSingleInstanceLock()) {
    app.quit();
    process.exit(0);
}

let mainWindow = null;
let port = 8000;

// Parse command line arguments to retrieve negotiated HTTP port
const portArgIndex = process.argv.indexOf('--port');
if (portArgIndex !== -1 && portArgIndex + 1 < process.argv.length) {
    port = parseInt(process.argv[portArgIndex + 1], 10);
}

function createWindow() {
    const primaryDisplay = screen.getPrimaryDisplay();
    const { width, height } = primaryDisplay.bounds;

    console.log(`[Electron main] Display Bounds: ${width}x${height}`);

    mainWindow = new BrowserWindow({
        width: width,
        height: height,
        x: 0,
        y: 0,
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        resizable: false,
        movable: false,
        minimizable: false,
        maximizable: false,
        skipTaskbar: true,
        hasShadow: false,
        backgroundColor: '#00000000', // Set background completely transparent
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    // Set always-on-top level: 'floating' keeps the orb above normal windows
    // but does NOT block the Windows taskbar auto-hide trigger zone.
    // ('screen-saver' was too aggressive and prevented taskbar from appearing)
    mainWindow.setAlwaysOnTop(true, 'floating');

    // Make the window click-through initially while still tracking mouse movement
    mainWindow.setIgnoreMouseEvents(true, { forward: true });

    // Clear session cache to force reload the modified HTML/JS files
    mainWindow.webContents.session.clearCache();

    // Use a timestamp cache-buster to prevent HTTP caching
    const url = `http://127.0.0.1:${port}/orb.html?platform=overlay&t=${Date.now()}`;
    console.log(`[Electron main] Loading URL: ${url}`);
    mainWindow.loadURL(url);

    // Start global mouse position tracking loop
    const mouseInterval = setInterval(() => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            const point = screen.getCursorScreenPoint();
            mainWindow.webContents.send('global-mouse-move', point);
        } else {
            clearInterval(mouseInterval);
        }
    }, 40);

    mainWindow.on('closed', () => {
        clearInterval(mouseInterval);
        mainWindow = null;
        app.quit();
    });
}

// IPC listener to toggle window interactivity dynamically
ipcMain.on('set-ignore-mouse-events', (event, ignore, options) => {
    const webContents = event.sender;
    const win = BrowserWindow.fromWebContents(webContents);
    if (win) {
        win.setIgnoreMouseEvents(ignore, options);
    }
});

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    app.quit();
});
