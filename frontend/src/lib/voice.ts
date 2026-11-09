// Half-duplex STT -> existing chat API -> TTS, with no audio persistence.
export type VoiceState = 'off' | 'listening' | 'thinking' | 'speaking';
type Result = { isFinal: boolean; 0: { transcript: string } };
interface Recognition {
  continuous: boolean; interimResults: boolean; lang: string;
  onresult: ((event: { results: ArrayLike<Result> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; abort(): void;
}
export interface VoiceIO {
  recognition(): Recognition;
  speak(text: string, language: string, end: () => void, error: () => void): void;
  cancelSpeech(): void;
}
export class VoiceConversation {
  private active = false;
  private generation = 0;
  private phase: VoiceState = 'off';
  private recognition: Recognition | null = null;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private silences = 0;
  private language = 'en-US';
  private io: VoiceIO;
  private send: (text: string) => Promise<string>;
  private state: (state: VoiceState) => void;
  private transcript: (text: string) => void;
  private error: (message: string) => void;
  constructor(io: VoiceIO, send: (text: string) => Promise<string>, state: (state: VoiceState) => void,
    transcript: (text: string) => void, error: (message: string) => void) {
    this.io = io; this.send = send; this.state = state; this.transcript = transcript; this.error = error;
  }
  private change(state: VoiceState) { this.phase = state; this.state(state); }
  private clearTimer() { clearTimeout(this.timer); this.timer = undefined; }
  stop() {
    this.active = false; this.generation++; this.clearTimer(); this.change('off');
    const recognition = this.recognition; this.recognition = null;
    recognition?.abort(); this.io.cancelSpeech();
  }
  start(language = 'en-US') {
    if (this.active) return;
    this.language = language; this.silences = 0; this.active = true; this.generation++;
    this.error(''); this.listen(this.generation);
  }
  private fail(message: string) { this.stop(); this.error(message); }
  private listen(generation: number) {
    if (!this.active || generation !== this.generation) return;
    this.change('listening'); this.transcript('');
    let recognition: Recognition;
    try { recognition = this.io.recognition(); }
    catch { this.fail('Speech recognition is unavailable. Use text chat or try another browser.'); return; }
    this.recognition = recognition;
    recognition.continuous = false; recognition.interimResults = true; recognition.lang = this.language;
    let submitted = false;
    const current = () => this.active && generation === this.generation && this.recognition === recognition;
    const silence = () => {
      if (!current() || this.phase !== 'listening' || submitted) return;
      this.clearTimer(); this.recognition = null; recognition.abort();
      if (++this.silences >= 2) this.fail('No speech detected. Check your microphone, then start voice again.');
      else this.listen(generation);
    };
    recognition.onresult = event => {
      if (!current() || submitted || this.phase !== 'listening') return;
      const results = Array.from(event.results);
      this.transcript(results.map(result => result[0].transcript).join(' ').trim());
      const text = results.filter(result => result.isFinal).map(result => result[0].transcript).join(' ').trim();
      if (text) { submitted = true; this.silences = 0; void this.answer(text, generation); }
    };
    recognition.onerror = event => {
      if (!current()) return;
      if (event.error === 'no-speech') { silence(); return; }
      this.fail(event.error === 'not-allowed' || event.error === 'service-not-allowed'
        ? 'Microphone permission denied. Allow it in browser settings, then start voice again.'
        : 'Speech recognition stopped. Check your microphone/network or use text chat.');
    };
    recognition.onend = silence;
    this.timer = setTimeout(silence, 30000);
    try { recognition.start(); }
    catch { this.fail('Could not start the microphone. Close other voice sessions and retry.'); }
  }
  private async answer(text: string, generation: number) {
    this.clearTimer(); this.change('thinking');
    const recognition = this.recognition; this.recognition = null; recognition?.abort();
    try {
      const reply = await this.send(text);
      if (!this.active || generation !== this.generation) return;
      this.change('speaking');
      let finished = false;
      const current = () => this.active && generation === this.generation && !finished;
      this.timer = setTimeout(() => { if (current()) this.fail('Speech playback timed out. Use text chat or restart voice.'); }, 90000);
      this.io.speak(reply, this.language, () => {
        if (!current()) return;
        finished = true; this.clearTimer(); this.listen(generation);
      }, () => { if (current()) this.fail('Speech playback failed. Your reply is saved in the chat.'); });
    } catch {
      if (this.active && generation === this.generation) this.fail('Message failed. Your draft is retained; use Retry message before restarting voice.');
    }
  }
}

export function browserVoiceIO(): VoiceIO | null {
  if (typeof window === 'undefined') return null;
  const browser = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  const Native = browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
  if (!Native || !('speechSynthesis' in window)) return null;
  return {
    recognition: () => new Native(),
    cancelSpeech: () => window.speechSynthesis.cancel(),
    speak: (text, language, end, error) => {
      const spoken = text.replace(/```[\s\S]*?```/g, ' Code example is in the chat. ')
        .replace(/\[S\d+\]/g, '').replace(/[*#`]/g, '').slice(0, 2000);
      const utterance = new SpeechSynthesisUtterance(spoken);
      utterance.lang = language; utterance.onend = end; utterance.onerror = error;
      window.speechSynthesis.speak(utterance);
    },
  };
}
