// ─────────────────────────────────────────────────────────────
//  VideoConcierge — the real-person concierge made from video clips.
//
//  Background clips (public/videos/), always muted and looping:
//    idle      → idle_loop.mp4
//    listening → listening.mp4   (optional; idle is used if missing)
//    thinking  → thinking.mp4    (optional; idle is used if missing)
//    speaking  → talking_base.mp4 (live answers, with Kokoro voice)
//
//  Premade answers: playClip(url) plays a library video WITH its own sound.
//  Library videos are downloaded in the background so they start instantly.
//  Two <video> layers cross-fade so changes never "jump".
// ─────────────────────────────────────────────────────────────

const CLIPS = {
  idle: '/videos/idle_loop.mp4',
  listening: '/videos/listening.mp4',
  thinking: '/videos/thinking.mp4',
  speaking: '/videos/talking_base.mp4',
};
const OPTIONAL = new Set(['/videos/listening.mp4', '/videos/thinking.mp4']);
const FADE_MS = 380;

export class VideoConcierge {
  constructor(container, { onProgress, onLoaded, onError } = {}) {
    this.container = container;
    this.state = 'idle';
    this.current = null;
    this.ready = false;
    this.clipPlaying = false; // true while a premade answer is on screen
    this.blobUrls = {};       // url -> blob URL (null = file missing)
    this.cancelClip = null;

    container.classList.add('video-concierge');
    this.layers = [this.#makeLayer(), this.#makeLayer()];
    this.front = 0;

    this.#preload(onProgress)
      .then(() => {
        this.ready = true;
        return this.#show(this.#clipFor(this.state), { instant: true });
      })
      .then(() => onLoaded?.())
      .catch((error) => {
        console.error(error);
        onError?.(error);
      });
  }

  /* ---------- public ---------- */

  setState(state) {
    this.state = state;
    if (!this.ready || this.clipPlaying) return;
    const clip = this.#clipFor(state);
    if (clip !== this.current) this.#show(clip);
  }

  // Download premade answer videos in the background (one at a time).
  async preloadLibrary(urls) {
    for (const url of urls) {
      if (url in this.blobUrls) continue;
      try {
        const response = await fetch(url);
        const type = response.headers.get('content-type') || '';
        this.blobUrls[url] = response.ok && type.startsWith('video/')
          ? URL.createObjectURL(await response.blob())
          : null;
      } catch {
        /* try again next time it is needed */
      }
    }
  }

  // true / false when known from the background download, undefined if not checked yet.
  hasClip(url) {
    if (!(url in this.blobUrls)) return undefined;
    return this.blobUrls[url] !== null;
  }

  // iPhone / iPad (Safari): a video may only play WITH sound if that element was
  // started by a tap once. Call this from a tap so later answers can play sound.
  unlockSound() {
    if (this.soundUnlocked) return;
    this.soundUnlocked = true;
    const fallback = this.blobUrls[CLIPS.idle] || CLIPS.idle;
    for (const video of this.layers) {
      if (!video.src) video.src = fallback; // needs a source to "play"
      const wasMuted = video.muted;
      const wasPaused = video.paused;
      video.muted = false;                  // background loops have no sound track
      video.play()
        .then(() => {
          if (!video.classList.contains('is-front') && wasPaused) video.pause();
        })
        .catch(() => { this.soundUnlocked = false; })
        .finally(() => { if (wasMuted && !this.clipPlaying) video.muted = true; });
    }
  }

  // Call before playing premade clips.
  beginClips() {
    this.clipPlaying = true;
  }

  // Play one premade answer video with sound. Resolves true when it finishes,
  // false if it was interrupted.
  playClip(url, { first = false } = {}) {
    this.clipPlaying = true;
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (fn, value) => {
        if (settled) return;
        settled = true;
        this.cancelClip = null;
        fn(value);
      };
      this.cancelClip = () => finish(resolve, false);

      this.#show(url, { loop: false, sound: true, fade: first ? FADE_MS : 140 })
        .then((video) => {
          if (!video) return finish(resolve, false);
          const cleanup = () => {
            video.removeEventListener('ended', done);
            video.removeEventListener('error', fail);
          };
          const done = () => { cleanup(); finish(resolve, true); };
          const fail = () => { cleanup(); finish(reject, new Error(`Could not play ${url}`)); };
          video.addEventListener('ended', done);
          video.addEventListener('error', fail);
          if (video.ended) done();
        })
        .catch((error) => finish(reject, error));
    });
  }

  // Called when premade clips are finished (or interrupted).
  endClips() {
    if (!this.clipPlaying) return; // already ended
    this.clipPlaying = false;
    this.cancelClip?.();
    for (const video of this.layers) {
      if (!video.muted) { video.pause(); video.muted = true; }
    }
    this.current = null;
    // After a premade answer she goes back to idle (not the talking loop).
    this.setState(this.state === 'speaking' ? 'idle' : this.state);
  }

  /* ---------- internals ---------- */

  #clipFor(state) {
    const clip = CLIPS[state] || CLIPS.idle;
    return this.blobUrls[clip] === null ? CLIPS.idle : clip; // optional clip missing
  }

  #makeLayer() {
    const video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;
    video.preload = 'auto';
    video.loop = true;
    video.disablePictureInPicture = true;
    video.className = 'concierge-video';
    this.container.appendChild(video);
    return video;
  }

  // Download background clips once so switching is instant.
  async #preload(onProgress) {
    const urls = [...new Set(Object.values(CLIPS))];
    let done = 0;
    await Promise.all(urls.map(async (url) => {
      const response = await fetch(url);
      const type = response.headers.get('content-type') || '';
      if (!response.ok || !type.startsWith('video/')) {
        if (!OPTIONAL.has(url)) throw new Error(`Missing video ${url}`);
        this.blobUrls[url] = null;
      } else {
        this.blobUrls[url] = URL.createObjectURL(await response.blob());
      }
      done += 1;
      onProgress?.(done / urls.length);
    }));
  }

  async #show(url, { instant = false, loop = true, sound = false, fade = FADE_MS } = {}) {
    this.current = url;
    const next = this.layers[1 - this.front];
    const prev = this.layers[this.front];

    next.loop = loop;
    next.muted = !sound;
    next.src = this.blobUrls[url] || url;
    next.currentTime = 0;
    try {
      await next.play();
    } catch (error) {
      if (this.current !== url) return null; // replaced while loading: not an error
      if (sound) throw error;                 // caller handles blocked audio
      console.warn('Video play blocked:', error);
    }
    if (this.current !== url) return null; // a newer change already took over

    const transition = instant ? 'none' : `opacity ${fade}ms ease`;
    next.style.transition = transition;
    prev.style.transition = transition;
    next.classList.add('is-front');
    prev.classList.remove('is-front');
    this.front = 1 - this.front;

    prev.muted = true;
    setTimeout(() => {
      if (!prev.classList.contains('is-front')) prev.pause();
    }, fade + 50);
    return next;
  }
}
