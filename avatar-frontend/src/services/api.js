import { CONFIG } from '../config.js';

// Where the backend (office PC) is. In order of priority:
//   1. ?api=https://... in the page address (remembered on this device; ?api= with nothing clears it)
//   2. public/backend.json  {"api": "https://..."}  - edit it on GitHub, the site picks it up on redeploy
//   3. VITE_API_BASE set on the hosting service when the site is built
//   4. CONFIG.API_BASE ('' = same address as the page, used when the PC serves the page itself)
const clean = (url) => (url || '').trim().replace(/\/+$/, '');

function savedApiBase() {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get('api');
    if (fromUrl !== null) {
      if (fromUrl.trim()) localStorage.setItem('saha-api-base', fromUrl.trim());
      else localStorage.removeItem('saha-api-base');
    }
    return localStorage.getItem('saha-api-base');
  } catch {
    return null; // storage blocked
  }
}

async function resolveApiBase() {
  const saved = savedApiBase();
  if (saved) return clean(saved);
  try {
    const response = await fetch(`/backend.json?t=${Date.now()}`, { cache: 'no-store', signal: AbortSignal.timeout(5000) });
    if (response.ok && (response.headers.get('content-type') || '').includes('json')) {
      const data = await response.json();
      if (data?.api) return clean(data.api);
    }
  } catch { /* no file: fall through */ }
  return clean(import.meta.env.VITE_API_BASE || CONFIG.API_BASE);
}

// Resolved once at start; every request waits for it.
export const apiBase = resolveApiBase();

// Extra header for ngrok addresses (skips ngrok's browser warning page).
async function request(path, options = {}) {
  const base = await apiBase;
  const headers = { ...(options.headers || {}) };
  if (base.includes('ngrok')) headers['ngrok-skip-browser-warning'] = '1';
  return fetch(`${base}${path}`, { ...options, headers });
}

// Ask the backend. Returns:
//   { source: 'library', answer, speech, videos: [...] }  -> play premade video(s)
//   { source: 'live',    answer, speech }                 -> voice + talking clip
export async function askConcierge(message, signal) {
  const response = await request('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!(response.headers.get('content-type') || '').includes('json')) {
    throw new Error('Failed to fetch: backend not reachable'); // got a web page, not the backend
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data?.detail) detail = data.detail;
    } catch { /* keep HTTP status */ }
    throw new Error(detail);
  }
  const data = await response.json();
  data.answer = cleanText(data.answer || '');
  data.speech = cleanText(data.speech || data.answer);
  if (!data.answer) throw new Error('The concierge returned an empty answer.');
  return data;
}

// Kokoro voice for live answers (null if unavailable).
export async function getVoice(text, signal) {
  try {
    const response = await request('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.blob();
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    console.warn('Voice unavailable:', error.message);
    return null;
  }
}

// True if a premade video file exists in public/videos/.
export async function videoExists(url) {
  try {
    const response = await fetch(url, { method: 'HEAD' });
    return response.ok && (response.headers.get('content-type') || '').startsWith('video/');
  } catch {
    return false;
  }
}

function cleanText(text) {
  return text
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/^#+\s*/gm, '')
    .replace(/^\s*[-•]\s+/gm, '• ')
    .trim();
}

// List of premade answers (to preload their videos).
export async function getLibrary() {
  try {
    const response = await request('/api/library', { signal: AbortSignal.timeout(8000) });
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

export async function checkHealth() {
  try {
    const response = await request('/health', { signal: AbortSignal.timeout(6000) });
    if (!response.ok) return false;
    const data = await response.json(); // a website page here (not JSON) means no backend
    return data?.status === 'healthy';
  } catch {
    return false;
  }
}
