const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    setIgnoreMouseEvents: (ignore, options) => {
        ipcRenderer.send('set-ignore-mouse-events', ignore, options);
    },
    onGlobalMouseMove: (callback) => {
        ipcRenderer.on('global-mouse-move', (event, point) => callback(point));
    }
});
