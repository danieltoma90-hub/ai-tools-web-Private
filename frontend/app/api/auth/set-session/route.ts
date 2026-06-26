import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json() as { access_token?: string; expires_at?: number };
  const { access_token, expires_at } = body;

  if (!access_token || typeof access_token !== "string") {
    return NextResponse.json({ error: "Invalid token" }, { status: 400 });
  }

  const maxAge = expires_at
    ? expires_at - Math.floor(Date.now() / 1000)
    : 3600;

  const response = NextResponse.json({ ok: true });
  response.cookies.set("auth-token", access_token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    maxAge: Math.max(maxAge, 0),
    path: "/",
  });
  return response;
}
