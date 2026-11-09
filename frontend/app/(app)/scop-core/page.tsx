"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import CapitolModeForm from "./CapitolModeForm";
import DocumentModeForm from "./DocumentModeForm";
import MinuteModeForm from "./MinuteModeForm";

type Mod = "document" | "capitol" | "minute";

const MODURI: { mod: Mod; icon: string; titlu: string; cand: string; detalii: string }[] = [
  {
    mod: "document",
    icon: "📘",
    titlu: "Document de scop complet",
    cand: "Pornești documentul de la zero.",
    detalii:
      "Cele 11 capitole — context, abordare, soluția pe module, analiza de acoperire, delimitări, " +
      "premise și validare. Documentul gazdă e opțional.",
  },
  {
    mod: "capitol",
    icon: "📎",
    titlu: "Doar capitolul CORE",
    cand: "Ai deja un document de scop (de ex. Producție).",
    detalii:
      "Capitolul standard „Charisma ERP CORE”, pe stilurile documentului tău, cu opțiunea de a-l " +
      "insera direct în el. Documentul gazdă e obligatoriu.",
  },
  {
    mod: "minute",
    icon: "📝",
    titlu: "Verifică documentul față de minute",
    cand: "Au avut loc ședințe după ce s-a scris documentul.",
    detalii:
      "Ce s-a cerut să se scoată și încă e acolo, ce s-a discutat și lipsește. Răspuns imediat, " +
      "fără model — fiecare punct e un extras din minută.",
  },
];

export default function ScopCorePage() {
  const [mod, setMod] = useState<Mod | null>(null);
  const [recentKey, setRecentKey] = useState(0);
  const ales = MODURI.find((m) => m.mod === mod);

  function documentNou() {
    setRecentKey((k) => k + 1);
  }

  return (
    <div className="p-6 max-w-5xl">
      <ToolCard
        icon="📄"
        title="Scop CORE"
        description="Documentul de scop Charisma ERP CORE — complet, doar capitolul de inserat, sau verificat față de minute"
        tool="scop-core"
        recentKey={recentKey}
      />

      {!ales ? (
        <div>
          <h3 className="text-sm font-bold text-[#18257f] mb-3">Ce vrei să faci?</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {MODURI.map((m) => (
              <button
                key={m.mod}
                onClick={() => setMod(m.mod)}
                className="text-left bg-white border border-[#e2e5f0] rounded-xl p-4 hover:border-[#18257f] hover:shadow-sm transition-all flex flex-col gap-2"
              >
                <span className="text-2xl" aria-hidden>
                  {m.icon}
                </span>
                <span className="text-sm font-bold text-[#1e3a5f]">{m.titlu}</span>
                <span className="text-xs font-medium text-[#18257f]">{m.cand}</span>
                <span className="text-xs text-slate-500 leading-relaxed">{m.detalii}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3 mb-4 bg-white border border-[#e2e5f0] rounded-xl px-4 py-3">
            <span className="text-xl" aria-hidden>
              {ales.icon}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-[#1e3a5f]">{ales.titlu}</p>
              <p className="text-xs text-slate-500">{ales.detalii}</p>
            </div>
            <button
              onClick={() => setMod(null)}
              className="shrink-0 text-xs font-medium text-[#18257f] border border-[#c7ccf0] rounded-lg px-3 py-1.5 hover:bg-[#eef0f8]"
            >
              ← Altă variantă
            </button>
          </div>

          {mod === "document" ? (
            <DocumentModeForm onGenerated={documentNou} />
          ) : mod === "capitol" ? (
            <CapitolModeForm onGenerated={documentNou} />
          ) : (
            <MinuteModeForm />
          )}
        </>
      )}
    </div>
  );
}
