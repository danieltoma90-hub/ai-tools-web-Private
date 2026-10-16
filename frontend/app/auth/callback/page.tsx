"use client";
import { useEffect, useState } from "react";

export default function AuthCallback() {
  const [msg, setMsg] = useState("Se procesează...");

  useEffect(() => {
    const hash = window.location.hash.substring(1);
    const params = new URLSearchParams(hash);
    const access_token = params.get("access_token");
    const error = params.get("error_description");

    if (error || !access_token) {
      setMsg("Link invalid sau expirat.");
      // linkul (de resetare sau de invitație) a expirat: utilizatorul își cere singur unul nou
      setTimeout(() => {
        window.location.href = "/login/parola-uitata?eroare=link_expirat";
      }, 2000);
      return;
    }

    // linkul de resetare a parolei („Am uitat parola”): întâi parola nouă, apoi intrarea în cont
    if (params.get("type") === "recovery") {
      window.location.replace(`/auth/parola-noua#${hash}`);
      return;
    }

    const expires_in = params.get("expires_in");
    const expires_at = expires_in
      ? Math.floor(Date.now() / 1000) + parseInt(expires_in)
      : undefined;

    fetch("/api/auth/set-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        access_token,
        refresh_token: params.get("refresh_token") ?? undefined,
        expires_at,
      }),
    })
      .then((res) => {
        if (res.ok) {
          window.location.href = "/dashboard";
        } else {
          window.location.href = "/login?error=invalid_credentials";
        }
      })
      .catch(() => {
        window.location.href = "/login?error=server_error";
      });
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <p className="text-slate-500 text-sm">{msg}</p>
    </div>
  );
}
