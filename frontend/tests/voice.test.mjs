import test from 'node:test';
import assert from 'node:assert/strict';
import { VoiceConversation, browserVoiceIO } from '../src/lib/voice.ts';

const flush = () => new Promise(resolve => setImmediate(resolve));
function setup(t, send = async () => 'A cited answer [S1].') {
  const recognizers = [], speech = [], states = [], errors = [], transcripts = [];
  const io = {
    recognition() {
      const recognition = { start() { this.started = true; }, abort() { this.aborted = true; this.onend?.(); } };
      recognizers.push(recognition); return recognition;
    },
    speak(text, language, end, error) { speech.push({ text, language, end, error }); },
    cancelSpeech() {},
  };
  const voice = new VoiceConversation(io, send, state => states.push(state), text => transcripts.push(text), error => errors.push(error));
  t.after(() => voice.stop());
  const final = (recognition, text = 'Explain this function') => recognition.onresult({ results: [{ isFinal: true, 0: { transcript: text } }] });
  return { voice, recognizers, speech, states, errors, transcripts, final };
}

test('final speech submits once, stops STT through thinking/TTS, then resumes', async t => {
  let resolve, calls = 0;
  const f = setup(t, () => { calls++; return new Promise(done => { resolve = done; }); });
  f.voice.start(); f.voice.start();
  assert.equal(f.recognizers.length, 1);
  const first = f.recognizers[0];
  first.onresult({ results: [{ isFinal: false, 0: { transcript: 'Explain' } }] });
  assert.equal(calls, 0);
  f.final(first); f.final(first);
  assert.equal(calls, 1); assert.equal(first.aborted, true);
  assert.equal(f.states.at(-1), 'thinking');
  resolve('A cited answer.'); await flush();
  assert.equal(f.states.at(-1), 'speaking'); assert.equal(f.recognizers.length, 1);
  f.final(first, 'speaker echo'); assert.equal(calls, 1);
  f.speech[0].end(); f.speech[0].end();
  assert.equal(f.recognizers.length, 2); assert.equal(f.states.at(-1), 'listening');
});

test('Stop during inference ignores late completion without sending again', async t => {
  let resolve;
  const f = setup(t, () => new Promise(done => { resolve = done; }));
  f.voice.start(); f.final(f.recognizers[0]); f.voice.stop();
  resolve('Saved response'); await flush();
  assert.equal(f.speech.length, 0); assert.equal(f.states.at(-1), 'off');
});

test('failed request stops and offers manual retry without an automatic POST loop', async t => {
  let calls = 0;
  const f = setup(t, async () => { calls++; throw Error('network'); });
  f.voice.start(); f.final(f.recognizers[0]); await flush();
  assert.equal(calls, 1); assert.equal(f.states.at(-1), 'off');
  assert.match(f.errors.at(-1), /draft is retained/);
  f.voice.start(); assert.equal(f.recognizers.length, 2);
});

test('permission denial is actionable and does not loop', t => {
  const f = setup(t); f.voice.start();
  f.recognizers[0].onerror({ error: 'not-allowed' });
  assert.equal(f.states.at(-1), 'off'); assert.match(f.errors.at(-1), /permission denied/);
  assert.equal(f.recognizers.length, 1);
});

test('silence retries are bounded and ignore stale callbacks', t => {
  const f = setup(t); f.voice.start();
  const first = f.recognizers[0]; first.onend(); first.onend();
  assert.equal(f.recognizers.length, 2);
  f.recognizers[1].onerror({ error: 'no-speech' });
  assert.equal(f.states.at(-1), 'off'); assert.match(f.errors.at(-1), /No speech/);
});

test('speech playback failure preserves text response and stops', async t => {
  const f = setup(t); f.voice.start('ur-PK'); f.final(f.recognizers[0]); await flush();
  assert.equal(f.speech[0].language, 'ur-PK'); f.speech[0].error();
  assert.equal(f.states.at(-1), 'off'); assert.match(f.errors.at(-1), /reply is saved/);
});

test('missing native browser APIs leave text mode available', () => {
  assert.equal(browserVoiceIO(), null);
});

test('recognition initialization failure never leaves voice listening', t => {
  const states = [], errors = [];
  const voice = new VoiceConversation({ recognition() { throw Error('unsupported'); }, cancelSpeech() {}, speak() {} },
    async () => 'unused', state => states.push(state), () => {}, error => errors.push(error));
  t.after(() => voice.stop()); voice.start();
  assert.equal(states.at(-1), 'off'); assert.match(errors.at(-1), /unavailable/);
});

test('microphone and playback watchdogs prevent endless activity', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const f = setup(t); f.voice.start();
  t.mock.timers.tick(30000); t.mock.timers.tick(30000);
  assert.equal(f.states.at(-1), 'off');
  f.voice.start(); f.final(f.recognizers.at(-1)); await flush();
  t.mock.timers.tick(90000);
  assert.equal(f.states.at(-1), 'off'); assert.match(f.errors.at(-1), /playback timed out/);
});
