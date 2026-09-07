import { NextRequest, NextResponse } from "next/server";
import { setSessionCookies } from "@/lib/session";

export async function POST(request: NextRequest) {
  const body = (await request.json()) as {
    access_token?: string;
    refresh_token?: string;
    expires_at?: number;
  };
  const { access_token, refresh_token, expires_at } = body;

  if (!access_token || typeof access_token !== "string") {
    return NextResponse.json({ error: "Invalid token" }, { status: 400 });
  }

  const response = NextResponse.json({ ok: true });
  setSessionCookies(response, { access_token, refresh_token, expires_at });
  return response;
}
