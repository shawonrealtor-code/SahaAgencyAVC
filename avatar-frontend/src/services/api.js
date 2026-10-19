import { CONFIG } from '../config.js';

// Ask the backend. Returns:
//   { source: 'library', answer, speech, videos: [...] }  -> play premade video(s)
//   { source: 'live',    answer, speech }                 -> voice + talking clip
export async function askConcierge(message, signal) {
  const response = await fetch(`${CONFIG.API_BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    signal,
  });
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
    const response = await fetch(`${CONFIG.API_BASE}/api/tts`, {
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
    const response = await fetch(`${CONFIG.API_BASE}/api/library`, { signal: AbortSignal.timeout(8000) });
    return response.ok ? await response.json() : [];
  } catch {
    return [];
  }
}

export async function checkHealth() {
  try {
    const response = await fetch(`${CONFIG.API_BASE}/health`, { signal: AbortSignal.timeout(4000) });
    return response.ok;
  } catch {
    return false;
  }
}
