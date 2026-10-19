// ─────────────────────────────────────────────────────────────
//  MicrophoneButton
//  Big round button + a live circular sound wave while listening,
//  so visitors can see the microphone is hearing them.
// ─────────────────────────────────────────────────────────────

const LABELS = {
  idle: 'Tap to speak',
  listening: 'Tap to stop and send',
  thinking: 'Please wait',
  speaking: 'Tap to stop the answer',
};

export class MicrophoneButton {
  constructor({ button, canvas, onPress }) {
    this.button = button;
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.state = 'idle';
    this.levels = new Array(48).fill(0);

    button.addEventListener('click', () => onPress?.(this.state));
    const loop = () => {
      this.#draw();
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  setState(state) {
    this.state = state;
    this.button.setAttribute('aria-label', LABELS[state] || LABELS.idle);
    this.button.disabled = state === 'thinking';
    if (state === 'listening') this.#openMic();
    else this.#closeMic();
  }

  async #openMic() {
    if (this.stream) return;
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      if (this.state !== 'listening') return this.#closeMic();
      this.audioCtx = this.audioCtx || new AudioContext();
      await this.audioCtx.resume();
      this.source = this.audioCtx.createMediaStreamSource(this.stream);
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 512;
      this.analyser.smoothingTimeConstant = 0.6;
      this.source.connect(this.analyser);
      this.data = new Uint8Array(this.analyser.frequencyBinCount);
    } catch (error) {
      // The wave is only visual; speech recognition still works without it.
      console.warn('Sound wave unavailable:', error.message);
    }
  }

  #closeMic() {
    this.source?.disconnect();
    this.source = null;
    this.analyser = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  #draw() {
    const { ctx, canvas } = this;
    const size = canvas.width;
    const center = size / 2;
    ctx.clearRect(0, 0, size, size);

    const bars = this.levels.length;
    if (this.analyser && this.state === 'listening') {
      this.analyser.getByteFrequencyData(this.data);
      const usable = Math.floor(this.data.length * 0.45);
      for (let i = 0; i < bars; i += 1) {
        // Mirror so the wave is symmetric left/right.
        const k = i < bars / 2 ? i : bars - 1 - i;
        const bin = Math.floor((k / (bars / 2)) * usable) + 2;
        const value = this.data[bin] / 255;
        this.levels[i] += (value - this.levels[i]) * 0.35;
      }
    } else {
      for (let i = 0; i < bars; i += 1) this.levels[i] *= 0.85;
    }

    const inner = size * 0.205;
    const maxLength = size * 0.24;
    ctx.lineCap = 'round';
    ctx.lineWidth = size * 0.014;

    for (let i = 0; i < bars; i += 1) {
      const level = this.levels[i];
      if (level < 0.01) continue;
      const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
      const length = size * 0.012 + level * maxLength;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      ctx.strokeStyle = `rgba(201, 162, 77, ${0.35 + level * 0.65})`;
      ctx.beginPath();
      ctx.moveTo(center + cos * inner, center + sin * inner);
      ctx.lineTo(center + cos * (inner + length), center + sin * (inner + length));
      ctx.stroke();
    }
  }
}
