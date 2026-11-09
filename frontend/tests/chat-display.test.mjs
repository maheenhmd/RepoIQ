import test from 'node:test';
import assert from 'node:assert/strict';
import { frameBuffer, shouldFollow, prependScrollTop } from '../src/lib/chat-display.ts';
import { consumeChatStream } from '../src/lib/api.ts';

function setup() {
  let id = 0;
  const frames = new Map(), values = [];
  const buffer = frameBuffer(value => values.push(value), callback => {
    frames.set(++id, callback); return id;
  }, id => frames.delete(id));
  const paint = () => { const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach(fn => fn()); };
  return { buffer, frames, values, paint };
}

test('bursts publish once per frame, with no lost, duplicated or reordered text', () => {
  const f = setup();
  f.buffer.append('First'); assert.equal(f.frames.size, 1);
  f.paint(); assert.deepEqual(f.values, ['First']);
  for (const token of [' ', 'سلام', '\n```ts\n', 'x', '\n```']) f.buffer.append(token);
  assert.equal(f.frames.size, 1); f.paint();
  assert.deepEqual(f.values, ['First', 'First سلام\n```ts\nx\n```']);
});

test('completion discards queued provisional frames and trusts the final answer', async () => {
  const f = setup();
  const frame = (kind, data) => `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`;
  const final = await consumeChatStream(new Response(frame('delta', { text: 'Unverified' }) +
    frame('complete', { answer: 'Verified replacement', version: 2 })), f.buffer.append, () => {});
  f.buffer.close(); f.paint();
  assert.deepEqual(f.values, []); assert.equal(final.answer, 'Verified replacement');
});

test('cancellation flushes received text once; unmount discards it; retries start fresh', () => {
  const f = setup(); f.buffer.append('Partial'); f.buffer.close(true);
  f.buffer.append('late'); f.paint(); f.buffer.close(true);
  assert.deepEqual(f.values, ['Partial']); assert.equal(f.frames.size, 0);
  const unmounted = setup(); unmounted.buffer.append('Hidden'); unmounted.buffer.close(); unmounted.paint();
  assert.deepEqual(unmounted.values, []);
  const retry = setup(); retry.buffer.append('Retry'); retry.paint();
  assert.deepEqual(retry.values, ['Retry']);
});

test('follow stops on upward motion, resumes near bottom, and preserves prepend offset', () => {
  assert.equal(shouldFollow(900, 890, 1200, 300), true);
  assert.equal(shouldFollow(880, 900, 1200, 300), false);
  assert.equal(shouldFollow(400, 390, 1200, 300), false);
  assert.equal(shouldFollow(850, 840, 1200, 300), true);
  assert.equal(prependScrollTop(170, 1200, 1600), 570);
});
