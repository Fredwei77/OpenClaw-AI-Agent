/**
 * Preload Script - 安全桥接主进程和渲染进程
 * 在启用 contextIsolation 时安全地暴露 API 给渲染进程
 */

const { contextBridge, ipcRenderer } = require('electron');

// 暴露给渲染进程的安全 API
contextBridge.exposeInMainWorld('electronAPI', {
    // 后端状态
    getBackendStatus: () => ipcRenderer.invoke('backend:getStatus'),
    restartBackend: () => ipcRenderer.invoke('backend:restart'),

    // 系统信息
    getSystemInfo: () => ipcRenderer.invoke('system:getInfo'),

    // 窗口控制
    minimizeWindow: () => ipcRenderer.send('window:minimize'),
    maximizeWindow: () => ipcRenderer.send('window:maximize'),
    closeWindow: () => ipcRenderer.send('window:close'),

    // 事件监听
    onBackendStatusChange: (callback) => {
        ipcRenderer.on('backend:statusChange', (event, status) => callback(status));
    },

    onError: (callback) => {
        ipcRenderer.on('error', (event, error) => callback(error));
    },

    // 移除监听器
    removeAllListeners: (channel) => {
        ipcRenderer.removeAllListeners(channel);
    }
});

// 通知主进程渲染进程已就绪
window.addEventListener('DOMContentLoaded', () => {
    console.log('[Preload] DOM loaded, electronAPI ready');
});
