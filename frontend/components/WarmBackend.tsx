"use client";
import { useEffect } from "react";

/** Trezeste backend-ul Render (free tier adoarme dupa 15 min) in timp ce
 *  utilizatorul tasteaza credentialele — la login serverul e deja pornit. */
export default function WarmBackend() {
  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_API_URL;
    if (url) {
      fetch(`${url}/health`, { cache: "no-store" }).catch(() => {});
    }
  }, []);
  return null;
}
