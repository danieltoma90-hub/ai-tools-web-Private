"use client";
import { useState } from "react";

const MESAJE: Record<string, string> = {
  weak_password: "Parola nouă trebuie să aibă cel puțin 8 caractere.",
  same_password: "Parola nouă trebuie să fie diferită de cea veche.",
  link_expirat: "Linkul a expirat sau a fost deja folosit. Cere un link nou.",
  server_error: "Eroare de server. Încearcă din nou.",
};

/** Parola nouă, aleasă cu linkul primit pe email („Am uitat parola”). Sesiunea din link (în fragmentul
 *  adresei, deci necitită de server) se folosește doar la salvare; apoi utilizatorul intră în cont. */
export default function ParolaNouaPage() {
  const [parola, setParola] = useState("");
  const [confirmare, setConfirmare] = useState("");
  const [eroare, setEroare] = useState("");
  const [ocupat, setOcupat] = useState(false);

  async function salveaza(e: React.FormEvent) {
    e.preventDefault();
    setEroare("");
    if (parola.length < 8) return setEroare(MESAJE.weak_password);
    if (parola !== confirmare) return setEroare("Parolele nu coincid.");

    const link = new URLSearchParams(window.location.hash.substring(1));
    const access_token = link.get("access_token");
    if (!access_token) return setEroare(MESAJE.link_expirat);

    setOcupat(true);
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          access_token,
          refresh_token: link.get("refresh_token") ?? undefined,
          expires_in: Number(link.get("expires_in") || 0),
          parola,
        }),
      });
      if (res.ok) {
        window.history.replaceState(null, "", "/auth/parola-noua"); // jetonul nu rămâne în istoric
        window.location.href = "/dashboard";
        return;
      }
      const json = await res.json().catch(() => ({}));
      setEroare(MESAJE[json.error] ?? MESAJE.server_error);
    } catch {
      setEroare(MESAJE.server_error);
    } finally {
      setOcupat(false);
    }
  }

  const camp =
    "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]";

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-[#1e3a5f] italic">AI Tools</h1>
          <span className="inline-block h-[3px] w-14 bg-[#ffd500] mt-1" />
        </div>
        <form onSubmit={salveaza} className="space-y-4">
          <div>
            <h2 className="text-base font-semibold text-[#18257f]">Alege parola nouă</h2>
            <p className="text-sm text-gray-600 mt-1">Cel puțin 8 caractere. După salvare intri direct în cont.</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Parola nouă</label>
            <input
              type="password"
              autoComplete="new-password"
              value={parola}
              onChange={(e) => setParola(e.target.value)}
              className={camp}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirmă parola nouă</label>
            <input
              type="password"
              autoComplete="new-password"
              value={confirmare}
              onChange={(e) => setConfirmare(e.target.value)}
              className={camp}
              required
            />
          </div>
          {eroare && <p className="text-sm text-red-600">{eroare}</p>}
          <button
            type="submit"
            disabled={ocupat}
            className="w-full bg-[#18257f] text-white py-2 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-50"
          >
            {ocupat ? "Se salvează..." : "Salvează parola și intră în cont"}
          </button>
        </form>
        <p className="text-center mt-5">
          <a href="/login/parola-uitata" className="text-sm text-[#18257f] hover:underline">
            Cere un link nou
          </a>
        </p>
      </div>
    </div>
  );
}
