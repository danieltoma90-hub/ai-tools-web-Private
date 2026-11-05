"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import HistoryPanel from "@/components/HistoryPanel";
import CapitolModeForm from "./CapitolModeForm";
import DocumentModeForm from "./DocumentModeForm";
import MinuteModeForm from "./MinuteModeForm";

type Mod = "document" | "capitol" | "minute";

export default function ScopCorePage() {
  const [mod, setMod] = useState<Mod>("document");
  const [historyKey, setHistoryKey] = useState(0);

  function bumpHistory() {
    setHistoryKey((k) => k + 1);
  }

  return (
    <div className="flex h-screen">
      <div className="flex-1 p-6 overflow-auto">
        <ToolCard
          icon="📄"
          title="Scop CORE"
          description="Documentul de scop Charisma ERP CORE — complet, pe 11 capitole, sau doar capitolul de inserat într-un document existent"
          tool="scop-core"
        />

        <div className="flex rounded-lg border border-slate-200 overflow-hidden w-fit mb-3">
          <button
            onClick={() => setMod("document")}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              mod === "document"
                ? "bg-[#18257f] text-white"
                : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            📘 Document complet (11 capitole)
          </button>
          <button
            onClick={() => setMod("capitol")}
            className={`px-4 py-2 text-sm font-medium transition-colors border-l border-slate-200 ${
              mod === "capitol"
                ? "bg-[#18257f] text-white"
                : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            📎 Doar capitolul CORE, pentru inserare
          </button>
          <button
            onClick={() => setMod("minute")}
            className={`px-4 py-2 text-sm font-medium transition-colors border-l border-slate-200 ${
              mod === "minute"
                ? "bg-[#18257f] text-white"
                : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            📝 Din minutele ședințelor
          </button>
        </div>

        <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 leading-relaxed mb-4">
          {mod === "document"
            ? "Construiește documentul de scop integral — context, abordare, soluția pe module, analiza de acoperire, delimitări, premise și validare. Documentul gazdă e opțional aici."
            : mod === "capitol"
            ? "Generează doar capitolul standard „Charisma ERP CORE”, clonat pe stilurile unui document de scop existent (ex. Producție) — cu opțiunea de a-l insera direct în el. Documentul gazdă e obligatoriu în acest mod."
            : "Citește minutele ședințelor și spune ce din ele a rămas nesincronizat cu documentul de scop: ce s-a cerut să se scoată și încă e acolo, ce s-a discutat și lipsește, ce trebuie reformulat. Nu folosește model — răspunsul e imediat, iar fiecare punct e un extras, cuvânt cu cuvânt, din minută."}
        </p>

        {mod === "document" ? (
          <DocumentModeForm onGenerated={bumpHistory} />
        ) : mod === "capitol" ? (
          <CapitolModeForm onGenerated={bumpHistory} />
        ) : (
          <MinuteModeForm />
        )}
      </div>

      <HistoryPanel tool="scop-core" refreshKey={historyKey} />
    </div>
  );
}
