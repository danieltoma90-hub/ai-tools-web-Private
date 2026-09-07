"use client";
import { useState } from "react";
import { getProviderDiagnostics, type ProviderStatus } from "@/lib/api";

const STATE_STYLE: Record<string, { badge: string; label: string }> = {
  ok: { badge: "bg-green-100 text-green-800", label: "Funcțional" },
  cheie_invalida: { badge: "bg-red-100 text-red-800", label: "Cheie invalidă" },
  fara_credit: { badge: "bg-red-100 text-red-800", label: "Fără credite" },
  limita_atinsa: { badge: "bg-amber-100 text-amber-800", label: "Limită atinsă" },
  model_indisponibil: { badge: "bg-amber-100 text-amber-800", label: "Model indisponibil" },
  lipsa: { badge: "bg-slate-100 text-slate-600", label: "Neconfigurat" },
  eroare: { badge: "bg-red-100 text-red-800", label: "Eroare" },
};

export default function ProviderDiagnostics() {
  const [rows, setRows] = useState<ProviderStatus[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    setLoading(true);
    setError("");
    try {
      const res = await getProviderDiagnostics();
      setRows(res.providers);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Verificarea a eșuat");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-8 border-t border-slate-200 pt-6">
      <h2 className="text-sm font-bold text-[#18257f] mb-1">Stare chei AI</h2>
      <p className="text-xs text-slate-500 mb-3">
        Verifică dacă cheile configurate pe server funcționează. Se face câte un
        apel minimal către fiecare provider.
      </p>

      <button
        onClick={run}
        disabled={loading}
        className="border border-[#18257f] text-[#18257f] hover:bg-[#eef0f8] rounded-lg px-3.5 py-1.5 text-xs font-semibold disabled:opacity-40"
      >
        {loading ? "Se verifică..." : "Verifică acum"}
      </button>

      {error && (
        <p className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {rows && (
        <ul className="mt-4 flex flex-col gap-2">
          {rows.map((r) => {
            const style = STATE_STYLE[r.state] ?? STATE_STYLE.eroare;
            return (
              <li
                key={r.provider}
                className="border border-slate-200 rounded-lg p-3 bg-white"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-[#1e3a5f]">
                    {r.provider}
                  </span>
                  <span
                    className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${style.badge}`}
                  >
                    {style.label}
                  </span>
                </div>
                <p className="text-xs text-slate-600">{r.message}</p>
                {r.key_hint && (
                  <p className="text-[11px] text-slate-400 mt-1 font-mono">
                    cheie: {r.key_hint}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
