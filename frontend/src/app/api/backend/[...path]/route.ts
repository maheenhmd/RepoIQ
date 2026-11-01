import { NextRequest, NextResponse } from 'next/server';

// Fixed upstream and allowlisted routes: this is not an arbitrary URL proxy.
async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join('/');
  const uuid = '[0-9a-fA-F-]{36}';
  const allowed = request.method === 'GET'
    ? route === 'ready' || new RegExp(`^api/interviews/${uuid}(/report)?$`).test(route)
    : route === 'api/interviews/start' || new RegExp(`^api/interviews/${uuid}/answers$`).test(route);
  if (!allowed) return NextResponse.json({ detail: 'Route unavailable' }, { status: 404 });
  try {
    const body = request.method === 'POST' ? await request.text() : undefined;
    if (body && body.length > 30000) return NextResponse.json({ detail: 'Request too large' }, { status: 413 });
    const origin = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000';
    const upstream = await fetch(`${origin.replace(/\/$/, '')}/${route}`, {
      method: request.method, body, headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(230000), cache: 'no-store', redirect: 'error',
    });
    return new NextResponse(await upstream.text(), { status: upstream.status,
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store',
        ...(upstream.headers.get('retry-after') ? { 'Retry-After': upstream.headers.get('retry-after')! } : {}) } });
  } catch {
    return NextResponse.json({ detail: 'Backend unavailable or request timed out. Retry using the same request.' }, { status: 503 });
  }
}
export { proxy as GET, proxy as POST };
