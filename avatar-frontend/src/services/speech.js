import { CONFIG } from '../config.js';

// Chrome/Edge speech recognition — one transcript only.
// What the visitor sees on screen is exactly what gets sent.
export class SpeechInput {
  constructor({ onInterim, onFinal, onEnd, onError }) {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.supported = Boolean(Recognition);
    this.callbacks = { onInterim, onFinal, onEnd, onError };
    this.active = false;
    if (!this.supported) return;

    this.Recognition = Recognition;
  }

  start() {
    if (!this.supported || this.active) return;

    const recognition = new this.Recognition();
    recognition.lang = CONFIG.SPEECH_LANG;
    recognition.interimResults = true;
    recognition.continuous = false; // stops by itself when the visitor pauses
    recognition.maxAlternatives = 1;

    let finalText = '';
    let latestText = '';

    recognition.onresult = (event) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += piece;
        else interim += piece;
      }
      latestText = (finalText + ' ' + interim).replace(/\s+/g, ' ').trim();
      this.callbacks.onInterim?.(latestText);
    };

    recognition.onerror = (event) => {
      if (event.error === 'aborted') return;
      this.callbacks.onError?.(event.error);
    };

    recognition.onend = () => {
      this.active = false;
      this.recognition = null;
      const text = (finalText.trim() || latestText).trim();
      if (text && !this.cancelled) this.callbacks.onFinal?.(text);
      this.callbacks.onEnd?.(Boolean(text) && !this.cancelled);
    };

    this.cancelled = false;
    this.recognition = recognition;
    this.active = true;
    recognition.start();
  }

  // Stop listening and send what was heard.
  stop() {
    this.recognition?.stop();
  }

  // Stop listening and throw away what was heard.
  cancel() {
    this.cancelled = true;
    this.recognition?.abort();
  }
}

export function speechErrorMessage(code) {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return 'Microphone permission is blocked. Allow it in the browser and try again.';
    case 'no-speech':
      return "I didn't hear anything. Tap the microphone and try again.";
    case 'audio-capture':
      return 'No microphone was found. Check the microphone connection.';
    case 'network':
      return 'Speech recognition needs an internet connection.';
    default:
      return 'Voice recognition stopped. Please try again or type your question.';
  }
}
