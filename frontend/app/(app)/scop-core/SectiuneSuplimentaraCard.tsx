"use client";
import SelectorPlasare from "./SelectorPlasare";
import { SECTIUNI_CORE } from "./sectiuniCore";
import type { SuplimentarUI } from "./tipuri";

type Props = {
  element: SuplimentarUI;
  onModifica: (id: string, patch: Partial<SuplimentarUI>) => void;
  onSterge: (id: string) => void;
};

/** O secțiune adăugată peste standardul CORE — capitolul 4 al documentului complet. */
export default function SectiuneSuplimentaraCard({ element, onModifica, onSterge }: Props) {
  return (
    <div className="border border-slate-200 rounded-lg p-3 flex flex-col gap-2">
      <div className="flex items-start gap-2">
        <input
          type="text"
          value={element.titlu}
          onChange={(e) => onModifica(element.id, { titlu: e.target.value })}
          placeholder="Titlu (ex. Integrare cu platforma de eCommerce)"
          className="flex-1 border border-slate-300 rounded-lg px-2 py-1.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#18257f]"
        />
        <button
          type="button"
          onClick={() => onSterge(element.id)}
          className="shrink-0 text-xs text-slate-400 hover:text-red-600 px-2 py-1.5"
          title="Șterge această secțiune"
        >
          ✕ Șterge
        </button>
      </div>
      <textarea
        value={element.intro}
        onChange={(e) => onModifica(element.id, { intro: e.target.value })}
        rows={2}
        placeholder="Introducere"
        className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
      />
      <textarea
        value={element.puncte}
        onChange={(e) => onModifica(element.id, { puncte: e.target.value })}
        rows={3}
        placeholder={"Funcționalități — câte un punct pe linie"}
        className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
      />
      <textarea
        value={element.nota}
        onChange={(e) => onModifica(element.id, { nota: e.target.value })}
        rows={2}
        placeholder="Notă (opțional)"
        className="w-full border border-slate-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
      />
      <div className="flex items-center gap-2">
        <label className="text-xs font-semibold text-slate-500 shrink-0">Plasare:</label>
        <SelectorPlasare
          valoare={element.plasare}
          onChange={(v) => onModifica(element.id, { plasare: v })}
          sectiuniIncluse={SECTIUNI_CORE}
        />
      </div>
    </div>
  );
}
