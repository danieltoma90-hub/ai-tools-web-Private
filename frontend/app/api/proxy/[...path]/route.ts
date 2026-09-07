import { NextRequest, NextResponse } from "next/server";
import {
  AUTH_COOKIE,
  REFRESH_COOKIE,
  clearSessionCookies,
  refreshSession,
  setSessionCookies,
  type SupabaseSession,
} from "@/lib/session";

const BACKEND = process.env.NEXT_PUBLIC_API_URL;
// 58s: lasă Render să se trezească din sleep (30-60s cold start), sub maxDuration Vercel (60s)
const BACKEND_TIMEOUT_MS = 58_000;

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  if (!BACKEND) {
    return NextResponse.json({ detail: "Backend not configured" }, { status: 500 });
  }

  const token = request.cookies.get(AUTH_COOKIE)?.value;
  const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;
  if (!token && !refreshToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { path } = await context.params;
  const segment = path.join("/");
  const search = request.nextUrl.search;
  const backendUrl = `${BACKEND}/api/${segment}${search}`;

  const contentType = request.headers.get("Content-Type");
  const body =
    request.method !== "GET" ? await request.arrayBuffer() : undefined;

  const callBackend = async (bearer: string) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
    try {
      const outHeaders: HeadersInit = { Authorization: `Bearer ${bearer}` };
      if (contentType) outHeaders["Content-Type"] = contentType;
      return await fetch(backendUrl, {
        method: request.method,
        headers: outHeaders,
        body,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }
  };

  try {
    let res = token
      ? await callBackend(token)
      : new Response(null, { status: 401 });
    let renewed: SupabaseSession | null = null;
    let refreshFailed = false;

    // Sesiunea expiră după ~1 oră. În loc să arunce „Token invalid sau expirat"
    // în fața utilizatorului, schimbăm refresh token-ul pe unul nou și reluăm
    // cererea o singură dată.
    if (res.status === 401 && refreshToken) {
      renewed = await refreshSession(refreshToken);
      if (renewed) {
        res = await callBackend(renewed.access_token);
      } else {
        refreshFailed = true;
      }
    }

    const resBody = await res.arrayBuffer();
    const response = new NextResponse(resBody, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "application/json",
      },
    });
    if (renewed) setSessionCookies(response, renewed);
    // Refresh token respins de Supabase = sesiune moartă. Cookie-urile TREBUIE
    // șterse aici: cât timp rămân, middleware-ul le vede prezente, crede că
    // sesiunea e validă și trimite utilizatorul înapoi în aplicație — iar
    // pagina cere din nou datele, ia 401 și o ia de la capăt (buclă de refresh).
    if (refreshFailed) clearSessionCookies(response);
    return response;
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      return NextResponse.json(
        { detail: "Serverul nu a răspuns în timp util. Verificați conexiunea și reîncercați." },
        { status: 504 }
      );
    }
    const msg = e instanceof Error ? e.message : "Backend unreachable";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
