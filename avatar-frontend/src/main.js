import './style.css';
import { CONFIG } from './config.js';
import { VideoConcierge } from './components/VideoConcierge.js';
import { MicrophoneButton } from './components/MicrophoneButton.js';
import { ConversationPanel } from './components/ConversationPanel.js';
import { StatusIndicator } from './components/StatusIndicator.js';
import { askConcierge, getVoice, videoExists, checkHealth, getLibrary, apiBase, refreshApiBase } from './services/api.js';
import { SpeechInput, speechErrorMessage } from './services/speech.js';

// ─────────────────────────────────────────────────────────────
//  Saha AVC — the flow:
//  Visitor taps mic → Listening → Thinking → Speaking → back to idle
//  Speaking = a premade answer video (common questions)
//          or Kokoro voice + talking clip (everything else)
// ─────────────────────────────────────────────────────────────

const $ = (selector) => document.querySelector(selector);
const kiosk = $('#kiosk');
const audio = $('#answer-audio');
const loading = $('#avatar-loading');

let state = 'idle';
let request = null;     // the in-flight question (so it can be cancelled)
let answerUrl = null;   // current audio blob URL
let idleTimer = null;
let statusTimer = null;

/* ---------- components ---------- */

const avatar = new VideoConcierge($('#avatar'), {
  onProgress: (p) => {
    loading.querySelector('span:last-child').textContent =
      `Preparing your concierge… ${Math.round(p * 100)}%`;
  },
  onLoaded: () => {
    loading.hidden = true;
    kiosk.classList.add('avatar-ready');
    preloadAnswers();
  },
  onError: () => {
    loading.querySelector('span:last-child').textContent =
      'Could not load the concierge videos. Check the public/videos folder.';
    loading.querySelector('.spinner').hidden = true;
  },
});

const status = new StatusIndicator($('#status'), $('#status-text'));

const panel = new ConversationPanel({
  suggestions: CONFIG.SUGGESTIONS,
  onSuggestion: (text) => ask(text),
});

const mic = new MicrophoneButton({
  button: $('#mic-button'),
  canvas: $('#mic-wave'),
  onPress: handleMicPress,
});

const speech = new SpeechInput({
  onInterim: (text) => panel.showVisitor(text, { live: true }),
  onFinal: (text) => ask(text),
  onEnd: (heardSomething) => {
    if (!heardSomething && state === 'listening') {
      setState('idle');
      panel.reset();
      flashStatus("I didn't catch that — tap to try again");
    }
  },
  onError: (code) => {
    if (code === 'no-speech') return; // handled in onEnd
    setState('idle');
    panel.showError(speechErrorMessage(code));
  },
});

/* ---------- state ---------- */

function setState(next) {
  if (import.meta.env.DEV) console.debug('[AVC] state:', next);
  state = next;
  kiosk.dataset.state = next;
  avatar.setState(next);
  mic.setState(next);
  status.set(next);
  clearTimeout(statusTimer);
  scheduleIdleReset();
}

function flashStatus(text, ms = 3500) {
  status.set(state, text);
  clearTimeout(statusTimer);
  statusTimer = setTimeout(() => status.set(state), ms);
}

/* ---------- audio unlock (browsers need one tap first) ---------- */

// A tiny silent sound, played once from a tap, unlocks the voice on iPhone/iPad.
const SILENCE = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=';
let audioUnlocked = false;
function unlockAudio() {
  avatar.unlockSound();
  if (audioUnlocked) return;
  audioUnlocked = true;
  if (!audio.src) {
    audio.src = SILENCE;
    audio.play().then(() => audio.pause()).catch(() => { audioUnlocked = false; });
  }
}
for (const type of ['pointerdown', 'touchend', 'click', 'keydown']) {
  document.addEventListener(type, unlockAudio, { capture: true });
}

/* ---------- actions ---------- */

function handleMicPress(current) {
  unlockAudio();

  if (current === 'listening') {
    speech.stop(); // sends what was heard
    return;
  }

  if (current === 'speaking') {
    request?.abort();
    request = null;
    stopSpeaking();
    setState('idle');
    return;
  }

  if (current !== 'idle') return;

  if (!speech.supported) {
    panel.showError('Voice input needs Google Chrome or Microsoft Edge. You can type your question instead.');
    openTyping();
    return;
  }

  closeTyping();
  panel.showVisitor('', { live: true });
  panel.hideAnswer();
  setState('listening');
  speech.start();
}

async function ask(question) {
  const text = question.trim();
  if (!text) return;
  unlockAudio();

  speech.cancel();
  stopSpeaking();
  request?.abort();

  const controller = new AbortController();
  request = controller;
  const timeout = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT_MS);

  panel.showVisitor(text);
  panel.showThinking();
  setState('thinking');

  try {
    const result = await askConcierge(text, controller.signal);
    if (request !== controller) return; // a newer question replaced this one
    panel.showAnswer(result.answer);

    // 1) Premade answer video(s), if the files exist.
    if (result.source === 'library' && (await playPremade(result.videos, controller))) return;
    if (request !== controller) return;

    // 2) Live answer (or premade video missing): voice + talking clip.
    const voice = await getVoice(result.speech, controller.signal);
    if (request !== controller) return;
    if (!voice) {
      setState('idle');
      flashStatus('Answer ready (voice unavailable)', 5000);
      return;
    }
    await playAnswer(voice);
  } catch (error) {
    if (request !== controller) return;
    console.error(error);
    setState('idle');
    panel.showError(friendlyError(error));
  } finally {
    clearTimeout(timeout);
    if (request === controller) request = null;
  }
}

// Download every premade answer video in the background so answers start instantly.
async function preloadAnswers() {
  const library = await getLibrary();
  const urls = library.flatMap((entry) => entry.videos || []).map((v) => CONFIG.VIDEO_BASE + v);
  await avatar.preloadLibrary(urls);
  if (import.meta.env.DEV) {
    const missing = urls.filter((url) => avatar.hasClip(url) === false);
    console.debug(`[AVC] answer videos ready: ${urls.length - missing.length}/${urls.length}`, missing);
  }
}

// Play the premade answer video(s) one after another. Returns false if any file is missing.
async function playPremade(videos, controller) {
  const urls = (videos || []).map((v) => CONFIG.VIDEO_BASE + v);
  if (!urls.length) return false;
  const present = await Promise.all(urls.map((url) => avatar.hasClip(url) ?? videoExists(url)));
  if (present.includes(false)) {
    console.info('Premade video missing, using voice instead:', urls.filter((_, i) => !present[i]));
    return false;
  }
  if (request !== controller) return true;

  avatar.beginClips(); // keep the background clip from switching underneath
  setState('speaking');
  try {
    for (let i = 0; i < urls.length; i += 1) {
      const finished = await avatar.playClip(urls[i], { first: i === 0 });
      if (!finished || request !== controller) return true; // interrupted by the visitor
    }
    return true;
  } catch (error) {
    console.warn('Premade video failed:', error.message);
    return false; // fall back to voice
  } finally {
    avatar.endClips();
    if (request === controller && state === 'speaking') setState('idle');
  }
}

async function playAnswer(blob) {
  const url = URL.createObjectURL(blob);
  if (answerUrl) URL.revokeObjectURL(answerUrl);
  answerUrl = url;

  audio.src = url;

  try {
    await audio.play();
    setState('speaking');
  } catch (error) {
    console.warn('Autoplay blocked:', error);
    setState('idle');
    flashStatus('Tap anywhere, then ask again to hear the answer', 6000);
  }
}

function stopSpeaking() {
  if (avatar.clipPlaying) avatar.endClips();
  if (!audio.paused) audio.pause();
  audio.currentTime = 0;
}

audio.addEventListener('ended', () => {
  if (state === 'speaking') setState('idle');
});
audio.addEventListener('error', () => {
  if (state === 'speaking') {
    setState('idle');
    flashStatus('Could not play the voice answer');
  }
});

function friendlyError(error) {
  const message = String(error?.message || '');
  if (error?.name === 'AbortError') return 'That took too long. Please try asking again.';
  if (/ollama/i.test(message)) return "I'm having trouble thinking right now. Please make sure Ollama is running.";
  if (/kokoro/i.test(message)) return 'My voice service is unavailable. Please make sure Kokoro is running.';
  if (/failed to fetch|networkerror|load failed/i.test(message))
    return "I can't reach the concierge right now. Please try again in a moment, or call us at (703) 627-0444.";
  return 'Sorry, something went wrong. Please try again.';
}

function resetConversation() {
  speech.cancel();
  stopSpeaking();
  request?.abort();
  request = null;
  closeTyping();
  panel.reset();
  setState('idle');
}

/* ---------- typed questions ---------- */

const typeForm = $('#type-form');
const typeInput = $('#type-input');

function openTyping() {
  typeForm.hidden = false;
  kiosk.classList.add('typing-open');
  typeInput.focus();
}
function closeTyping() {
  typeForm.hidden = true;
  kiosk.classList.remove('typing-open');
}

$('#keyboard-toggle').addEventListener('click', () => {
  if (state === 'listening') {
    speech.cancel();
    panel.reset();
    setState('idle');
  }
  if (typeForm.hidden) openTyping();
  else closeTyping();
});

typeForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const text = typeInput.value;
  typeInput.value = '';
  ask(text);
});

$('#reset-button').addEventListener('click', resetConversation);

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') resetConversation();
});

/* ---------- idle reset ---------- */

function scheduleIdleReset() {
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    if (state === 'idle') {
      closeTyping();
      panel.reset();
    }
  }, CONFIG.IDLE_RESET_SECONDS * 1000);
}
['pointerdown', 'keydown'].forEach((type) =>
  document.addEventListener(type, scheduleIdleReset, { passive: true })
);

/* ---------- brand + clock ---------- */

const logo = $('#brand-logo');
logo.addEventListener('load', () => kiosk.classList.add('has-logo'));
logo.addEventListener('error', () => logo.remove());

const clock = $('#clock');
function updateClock() {
  const now = new Date();
  clock.textContent = now.toLocaleString([], {
    weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  });
}
updateClock();
setInterval(updateClock, 15000);

/* ---------- contact strip ---------- */

const ICONS = {
  phone: '<path d="M5 4h3.5l1.5 4-2 1.3a11 11 0 0 0 6.7 6.7L16 14l4 1.5V19a1.5 1.5 0 0 1-1.6 1.5A16 16 0 0 1 3.5 5.6 1.5 1.5 0 0 1 5 4z"/>',
  address: '<path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  hours: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  website: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.5 2.6 2.5 14.4 0 17M12 3.5c-2.5 2.6-2.5 14.4 0 17"/>',
};
const contact = $('#contact');
for (const key of ['phone', 'address', 'hours', 'website']) {
  const value = CONFIG.CONTACT?.[key];
  if (!value) continue;
  const item = document.createElement('span');
  item.className = `contact-item is-${key}`;
  item.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[key]}</svg>`;
  const text = document.createElement(key === 'phone' ? 'strong' : 'span');
  text.textContent = value;
  item.appendChild(text);
  contact.appendChild(item);
}

/* ---------- start ---------- */

setState('idle');
async function watchBackend() {
  let ok = await checkHealth();
  if (!ok) {                       // offline: look for a working address again
    await refreshApiBase();
    ok = await checkHealth();
  }
  kiosk.classList.toggle('offline', !ok);
  const shown = $('#status').dataset.state;
  if (state === 'idle' && (!ok || shown === 'offline')) status.set(ok ? 'idle' : 'offline');
}
apiBase().then((base) => console.info('[AVC] backend:', base || '(same address as this page)'));
watchBackend();
setInterval(() => { if (state === 'idle') watchBackend(); }, 30000);
