"use client";
import { useState } from "react";
import ToolCard from "@/components/ToolCard";
import HistoryPanel from "@/components/HistoryPanel";
import CapitolModeForm from "./CapitolModeForm";
import DocumentModeForm from "./DocumentModeForm";

type Mod = "document" | "capitol";

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
        </div>

        <p className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 leading-relaxed mb-4">
          {mod === "document"
            ? "Construiește documentul de scop integral — context, abordare, soluția pe module, analiza de acoperire, delimitări, premise și validare. Documentul gazdă e opțional aici."
            : "Generează doar capitolul standard „Charisma ERP CORE”, clonat pe stilurile unui document de scop existent (ex. Producție) — cu opțiunea de a-l insera direct în el. Documentul gazdă e obligatoriu în acest mod."}
        </p>

        {mod === "document" ? (
          <DocumentModeForm onGenerated={bumpHistory} />
        ) : (
          <CapitolModeForm onGenerated={bumpHistory} />
        )}
      </div>

      <HistoryPanel tool="scop-core" refreshKey={historyKey} />
    </div>
  );
}
