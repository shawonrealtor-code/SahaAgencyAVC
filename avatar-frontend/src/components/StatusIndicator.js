// Small pill above the conversation: Tap to speak · Listening… · Thinking… · Speaking…

const TEXT = {
  idle: 'Tap to speak',
  listening: 'Listening…',
  thinking: 'Let me think…',
  speaking: 'Speaking…',
  offline: 'Concierge offline — check Docker',
};

export class StatusIndicator {
  constructor(element, textElement) {
    this.element = element;
    this.textElement = textElement;
  }

  set(state, customText) {
    this.element.dataset.state = state;
    this.textElement.textContent = customText || TEXT[state] || TEXT.idle;
  }
}
