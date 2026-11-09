// One publish per paint, preserving provider order without simulating typing.
export function frameBuffer(publish: (text: string) => void,
  schedule: (callback: FrameRequestCallback) => number = requestAnimationFrame,
  cancel: (id: number) => void = cancelAnimationFrame) {
  let text = '', frame: number | null = null, closed = false;
  const flush = () => { frame = null; if (!closed) publish(text); };
  return {
    append(delta: string) {
      if (closed) return;
      text += delta;
      if (frame === null) frame = schedule(flush);
    },
    close(flushPending = false) {
      if (closed) return;
      if (frame !== null) cancel(frame);
      frame = null;
      if (flushPending) publish(text);
      closed = true;
      text = '';
    },
  };
}

export function shouldFollow(top: number, previousTop: number, height: number, viewport: number) {
  return top >= previousTop && height - viewport - top <= 80;
}

export function prependScrollTop(top: number, previousHeight: number, height: number) {
  return top + height - previousHeight;
}
