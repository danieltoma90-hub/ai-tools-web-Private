import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL;
const BACKEND_TIMEOUT_MS = 270_000; // 270s — sub limita maxDuration de 300s

export const maxDuration = 300; // Vercel Pro: permite funcții până la 300s

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  if (!BACKEND) {
    return NextResponse.json({ detail: "Backend not configured" }, { status: 500 });
  }

  const token = request.cookies.get("auth-token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  const { path } = await context.params;
  const segment = path.join("/");
  const search = request.nextUrl.search;
  const backendUrl = `${BACKEND}/api/${segment}${search}`;

  const outHeaders: HeadersInit = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("Content-Type");
  if (contentType) outHeaders["Content-Type"] = contentType;

  const body =
    request.method !== "GET" ? await request.arrayBuffer() : undefined;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const res = await fetch(backendUrl, {
      method: request.method,
      headers: outHeaders,
      body,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    const resBody = await res.arrayBuffer();
    return new NextResponse(resBody, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "application/json",
      },
    });
  } catch (e) {
    clearTimeout(timeoutId);
    if (e instanceof Error && e.name === "AbortError") {
      return NextResponse.json(
        { detail: "Serverul nu a răspuns în timp util (270s). Încercați din nou." },
        { status: 504 }
      );
    }
    const msg = e instanceof Error ? e.message : "Backend unreachable";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
