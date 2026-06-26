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
      setTimeout(() => {
        window.location.href = "/login?error=invalid_credentials";
      }, 2000);
      return;
    }

    const expires_in = params.get("expires_in");
    const expires_at = expires_in
      ? Math.floor(Date.now() / 1000) + parseInt(expires_in)
      : undefined;

    fetch("/api/auth/set-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token, expires_at }),
    })
      .then((res) => {
        if (res.ok) {
          window.location.href = "/minuta";
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
