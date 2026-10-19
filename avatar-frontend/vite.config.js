import { defineConfig } from 'vite';

// The screen talks to the backend through this server (same address as the page),
// so it works from any device: the PC itself, a tablet/phone on the Wi-Fi,
// or a public address (e.g. a Cloudflare tunnel). The backend stays private on the PC.
const BACKEND = 'http://127.0.0.1:8081';

const proxy = {
  '/api': { target: BACKEND, changeOrigin: true },
  '/health': { target: BACKEND, changeOrigin: true },
};

export default defineConfig({
  server: {
    host: true,         // also reachable from other devices on the network
    port: 5173,
    allowedHosts: true, // allow custom domains / tunnels
    proxy,
  },
  preview: {
    host: true,
    port: 5173,
    allowedHosts: true,
    proxy,
  },
});
