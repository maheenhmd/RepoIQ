import test from 'node:test';
import assert from 'node:assert/strict';
import { consumeChatStream, streamChat, ApiError } from '../src/lib/api.ts';

const frame = (kind, data) => `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`;
test('UTF-8 packets stream progressively and complete only on server confirmation', async () => {
  let writer;
  const response = new Response(new ReadableStream({ start(controller) { writer = controller; } }));
  const deltas = [], stages = [], encoder = new TextEncoder();
  let completed = false;
  const result = consumeChatStream(response, text => deltas.push(text), stage => stages.push(stage)).then(value => { completed = true; return value; });
  const packet = encoder.encode(frame('status', { stage: 'generating' })+frame('delta', { text: 'سلام [S1]' }));
  for (const byte of packet) writer.enqueue(new Uint8Array([byte]));
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(deltas, ['سلام [S1]']); assert.deepEqual(stages, ['generating']); assert.equal(completed, false);
  writer.enqueue(encoder.encode(frame('complete', { answer: 'Verified', version: 1 })));
  assert.equal((await result).version, 1);
});

test('EOF never converts partial text into a saved answer', async () => {
  const response = new Response(frame('delta', { text: 'Partial' }));
  await assert.rejects(consumeChatStream(response, () => {}, () => {}), /Stream interrupted/);
});

test('validation and busy errors preserve their actionable status', async () => {
  for (const status of [429, 502]) {
    await assert.rejects(consumeChatStream(new Response(frame('error', { status, detail: 'Retry safely' })), () => {}, () => {}),
      error => error instanceof ApiError && error.status === status);
  }
});

test('shared inference guard blocks duplicates and recovers after a stopped stream', async t => {
  const original = globalThis.fetch;
  t.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async (_, options) => new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(Error('aborted')), { once: true }));
  const controller = new AbortController();
  const first = streamChat('api/chats/a/b/messages/stream', {}, () => {}, () => {}, controller.signal);
  await assert.rejects(streamChat('api/chats/a/b/messages/stream', {}, () => {}, () => {}, new AbortController().signal), error => error.status === 429);
  controller.abort(); await assert.rejects(first, /draft is saved/);
  globalThis.fetch = async () => new Response(frame('complete', { version: 1 }));
  assert.equal((await streamChat('api/chats/a/b/messages/stream', {}, () => {}, () => {}, new AbortController().signal)).version, 1);
});
