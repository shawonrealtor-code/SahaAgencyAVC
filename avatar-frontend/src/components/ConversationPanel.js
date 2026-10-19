// ─────────────────────────────────────────────────────────────
//  ConversationPanel — greeting, live visitor text, answer text,
//  and quick-tap suggestion chips.
// ─────────────────────────────────────────────────────────────

export class ConversationPanel {
  constructor({ suggestions, onSuggestion }) {
    this.el = {
      greeting: document.querySelector('#greeting'),
      visitorTurn: document.querySelector('#visitor-turn'),
      visitorText: document.querySelector('#visitor-text'),
      conciergeTurn: document.querySelector('#concierge-turn'),
      conciergeText: document.querySelector('#concierge-text'),
      suggestions: document.querySelector('#suggestions'),
    };

    for (const text of suggestions) {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'chip';
      chip.textContent = text;
      chip.addEventListener('click', () => onSuggestion?.(text));
      this.el.suggestions.appendChild(chip);
    }
  }

  // Visitor's words (live while speaking, then final).
  showVisitor(text, { live = false } = {}) {
    this.el.greeting.hidden = true;
    this.el.suggestions.hidden = true;
    this.el.visitorTurn.hidden = false;
    this.el.visitorText.textContent = text || '…';
    this.el.visitorTurn.classList.toggle('is-live', live);
  }

  showThinking() {
    this.el.conciergeTurn.hidden = false;
    this.el.conciergeTurn.classList.remove('is-error');
    this.el.conciergeText.innerHTML =
      '<span class="typing" aria-label="Thinking"><i></i><i></i><i></i></span>';
  }

  showAnswer(text) {
    this.el.conciergeTurn.hidden = false;
    this.el.conciergeTurn.classList.remove('is-error');
    this.el.conciergeText.textContent = text;
    this.el.conciergeText.scrollTop = 0;
  }

  showError(text) {
    this.el.greeting.hidden = true;
    this.el.conciergeTurn.hidden = false;
    this.el.conciergeTurn.classList.add('is-error');
    this.el.conciergeText.textContent = text;
  }

  hideAnswer() {
    this.el.conciergeTurn.hidden = true;
  }

  reset() {
    this.el.greeting.hidden = false;
    this.el.suggestions.hidden = false;
    this.el.visitorTurn.hidden = true;
    this.el.conciergeTurn.hidden = true;
    this.el.visitorText.textContent = '';
    this.el.conciergeText.textContent = '';
  }
}
