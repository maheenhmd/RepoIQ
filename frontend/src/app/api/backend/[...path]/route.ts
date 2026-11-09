import { NextRequest, NextResponse } from 'next/server';

// Fixed upstream and allowlisted routes: this is not an arbitrary URL proxy.
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join('/');
  const uuid = '[0-9a-fA-F-]{36}';
  const chatGet = new RegExp(`^api/chats/${uuid}/${uuid}$`).test(route);
  const chatStream = new RegExp(`^api/chats/${uuid}/${uuid}/messages/stream$`).test(route);
  const chatPost = route === 'api/chats' || chatStream || new RegExp(`^api/chats/${uuid}/${uuid}/messages$`).test(route);
  const allowed = request.method === 'DELETE'
    ? new RegExp(`^api/interviews/${uuid}$`).test(route)
    : request.method === 'GET'
    ? route === 'ready' || new RegExp(`^api/interviews/${uuid}(/report)?$`).test(route)
      || chatGet || new RegExp(`^api/repositories/(ingest/${uuid}|${uuid}/ready)$`).test(route)
    : chatPost || ['api/interviews/start', 'api/repositories/ingest', 'api/repositories/lookup', 'api/interviews/lookup'].includes(route) || new RegExp(`^api/interviews/${uuid}/answers$`).test(route);
  if (!allowed) return NextResponse.json({ detail: 'Route unavailable' }, { status: 404 });
  try {
    const body = request.method === 'POST' ? await request.text() : undefined;
    if (body && body.length > 30000) return NextResponse.json({ detail: 'Request too large' }, { status: 413 });
    const origin = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';
    const before = chatGet ? request.nextUrl.searchParams.get('before') : null;
    const query = before && /^\d{1,18}$/.test(before) ? `?before=${before}` : '';
    const upstream = await fetch(`${origin.replace(/\/$/, '')}/${route}${query}`, {
      method: request.method, body, headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(230000)]), cache: 'no-store', redirect: 'error',
    });
    return new NextResponse(upstream.status === 204 ? null : chatStream && upstream.ok ? upstream.body : await upstream.text(), { status: upstream.status,
      headers: { 'Content-Type': chatStream && upstream.ok ? 'text/event-stream' : 'application/json', 'Cache-Control': 'no-store, no-transform',
        ...(chatStream ? { 'X-Accel-Buffering': 'no' } : {}),
        ...(upstream.headers.get('retry-after') ? { 'Retry-After': upstream.headers.get('retry-after')! } : {}) } });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable or request timed out. Retry using the same request.' }, { status: 503 });
  }
}
export { proxy as GET, proxy as POST, proxy as DELETE };
