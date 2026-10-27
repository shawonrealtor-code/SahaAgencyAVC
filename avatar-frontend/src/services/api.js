import { CONFIG } from '../config.js';

// Where the backend (office PC) is. Candidates, in order:
//   1. ?api=https://... in this page address (for testing; ?api= with nothing clears a remembered one)
//   2. public/backend.json  {"api": "https://..."}  - the site's setting, edited on GitHub
//   3. an address remembered on this device from an earlier ?api= link
//   4. VITE_API_BASE at build time, or CONFIG.API_BASE ('' = same address as the page)
// The first one that answers /health is used. A remembered address that no longer works is
// forgotten, so devices never get stuck on an old tunnel address.
const clean = (url) => (url || '').trim().replace(/\/+$/, '');
const SAVED_KEY = 'saha-api-base';

function store(fn) {
  try { return fn(localStorage); } catch { return null; } // storage blocked
}

function headersFor(base) {
  return base.includes('ngrok') ? { 'ngrok-skip-browser-warning': '1' } : {};
}

async function healthy(base) {
  try {
    const response = await fetch(`${base}/health`, { headers: headersFor(base), signal: AbortSignal.timeout(6000) });
    if (!response.ok) return false;
    return (await response.json())?.status === 'healthy';
  } catch {
    return false;
  }
}

async function siteSetting() {
  try {
    const response = await fetch(`/backend.json?t=${Date.now()}`, { cache: 'no-store', signal: AbortSignal.timeout(5000) });
    if (response.ok && (response.headers.get('content-type') || '').includes('json')) {
      return clean((await response.json())?.api);
    }
  } catch { /* no file */ }
  return '';
}

async function resolveApiBase() {
  const fromUrl = new URLSearchParams(window.location.search).get('api');
  if (fromUrl !== null) {
    store((s) => (fromUrl.trim() ? s.setItem(SAVED_KEY, fromUrl.trim()) : s.removeItem(SAVED_KEY)));
  }
  const saved = clean(store((s) => s.getItem(SAVED_KEY)));
  const setting = await siteSetting();
  const candidates = [...new Set([
    fromUrl?.trim() ? clean(fromUrl) : null,
    setting || null,
    saved || null,
    clean(import.meta.env.VITE_API_BASE || CONFIG.API_BASE),
  ].filter((c) => typeof c === 'string'))];

  for (const base of candidates) {
    if (await healthy(base)) {
      if (saved && base !== saved) store((s) => s.removeItem(SAVED_KEY)); // forget a dead old address
      return base;
    }
  }
  return candidates[0]; // nothing answers right now; keep trying this one
}

let current = resolveApiBase();

// The address in use (a promise). Call refreshApiBase() to look again, e.g. after going offline.
export function apiBase() {
  return current;
}
export function refreshApiBase() {
  current = resolveApiBase();
  return current;
}

async function request(path, options = {}) {
  const base = await current;
  const headers = { ...(options.headers || {}), ...headersFor(base) };
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
