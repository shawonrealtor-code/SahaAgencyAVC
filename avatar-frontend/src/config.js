// ─────────────────────────────────────────────────────────────
//  Saha AVC — screen settings. Change values here only.
// ─────────────────────────────────────────────────────────────

export const CONFIG = {
  // Backend address. Leave empty: the screen server forwards /api to the
  // Docker backend (see vite.config.js), so phones and other devices work too.
  API_BASE: '',

  // Where premade answer videos live (inside public/videos/).
  VIDEO_BASE: '/videos/',

  // Browser speech recognition language.
  SPEECH_LANG: 'en-US',

  // After this many seconds with no activity, the screen resets.
  IDLE_RESET_SECONDS: 90,

  // How long to wait for an answer before giving up (ms).
  REQUEST_TIMEOUT_MS: 180000,

  // Quick-tap questions shown under the greeting (portrait screens show the first 3).
  // Each one has a premade video, so it answers instantly.
  SUGGESTIONS: [
    'What insurance do you offer?',
    'How can I get a quote?',
    'Where is your office?',
    'What are your hours?',
    'How do I file a claim?',
    'Do you offer business insurance?',
  ],

  // Contact details shown on screen.
  CONTACT: {
    phone: '(703) 627-0444',
    address: '14484 General Washington Dr, Woodbridge, VA 22193',
    hours: 'Monday – Friday',
    website: 'sahaagency.com',
  },
};
