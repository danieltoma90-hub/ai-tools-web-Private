"use client";
import { useEffect, useState } from "react";
import { getJurnalErori, type IntrareJurnal } from "@/lib/api";

const MODULE: Record<string, string> = {
  minuta: "Minută",
  mockup: "Mockup",
  scenarii: "Scenarii",
  "scop-core": "Scop CORE",
  training: "Training",
};

function cand(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleString("ro-RO", {
        day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
      });
}

/** Ultimele generări eșuate — când un coleg spune „nu merge", răspunsul e aici. */
export default function JurnalErori() {
  const [intrari, setIntrari] = useState<IntrareJurnal[] | null>(null);
  const [eroare, setEroare] = useState("");

  function incarca() {
    setEroare("");
    getJurnalErori()
      .then((r) => setIntrari(r.intrari))
      .catch((e) => setEroare(e instanceof Error ? e.message : "Jurnalul nu a putut fi citit"));
  }

  useEffect(incarca, []);

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-bold text-[#18257f]">
          Jurnal de erori{intrari ? ` (${intrari.length})` : ""}
        </h2>
        <button onClick={incarca} className="text-xs text-[#18257f] hover:underline">
          Reîncarcă
        </button>
      </div>
      <p className="text-xs text-slate-500">
        Ultimele generări eșuate: cine, ce modul și de ce. Primul rând e textul pe care
        l-a văzut utilizatorul; detaliul tehnic e pentru tine.
      </p>

      {eroare && <p className="text-xs text-red-700">{eroare}</p>}
      {intrari && intrari.length === 0 && (
        <p className="text-xs text-emerald-700">Nicio generare eșuată.</p>
      )}

      {intrari && intrari.length > 0 && (
        <div className="bg-white border border-[#e2e5f0] rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#f2f4fb] text-left text-xs text-slate-600">
              <tr>
                <th className="px-4 py-2 whitespace-nowrap">Când</th>
                <th className="px-4 py-2">Modul</th>
                <th className="px-4 py-2">Utilizator</th>
                <th className="px-4 py-2">Ce s-a întâmplat</th>
              </tr>
            </thead>
            <tbody>
              {intrari.map((i, k) => (
                <tr key={`${i.cand}-${k}`} className="border-t border-slate-100 align-top">
                  <td className="px-4 py-2 text-xs text-slate-500 whitespace-nowrap">{cand(i.cand)}</td>
                  <td className="px-4 py-2 text-xs whitespace-nowrap">{MODULE[i.modul] ?? i.modul}</td>
                  <td className="px-4 py-2 text-xs">{i.email}</td>
                  <td className="px-4 py-2 text-xs">
                    <p className="text-slate-700">{i.mesaj}</p>
                    {i.tehnic && i.tehnic !== i.mesaj && (
                      <details className="mt-1">
                        <summary className="text-[11px] text-slate-400 cursor-pointer">detaliu tehnic</summary>
                        <p className="text-[11px] text-slate-500 font-mono break-all mt-1">{i.tehnic}</p>
                      </details>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
