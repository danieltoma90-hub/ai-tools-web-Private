"use client";
import { useEffect, useRef } from "react";

export type ColoanaTabel<T> = {
  cheie: keyof T & string;
  eticheta: string;
  placeholder?: string;
  tip?: "text" | "textarea" | "select";
  optiuni?: { valoare: string; eticheta: string }[];
  /** Clasă Tailwind pentru lățimea coloanei (ex. "w-28"); implicit se împarte egal. */
  clasa?: string;
};

type Props<T extends { id: string }> = {
  randuri: T[];
  coloane: ColoanaTabel<T>[];
  onModifica: (id: string, cheie: keyof T & string, valoare: string) => void;
  onAdauga: () => void;
  onSterge: (id: string) => void;
  etichetaAdauga?: string;
  golMesaj?: string;
};

/**
 * Tabel editabil generic — matricea de acoperire, delimitarea față de documentul-frate și
 * fluxul operațional sunt toate „rânduri de text pe câteva coloane, cu ștergere fără
 * confirmare”. Gândit pentru 20-60 de rânduri (Christof a avut 65 de cerințe):
 *
 * - Enter într-un câmp al ULTIMULUI rând adaugă un rând nou și mută focusul pe primul lui
 *   câmp — utilizatorul poate completa un tabel întreg fără să atingă mouse-ul.
 * - Ștergerea unui rând e imediată (✕), fără `confirm()` — la 40 de rânduri, o confirmare la
 *   fiecare ștergere ar fi enervantă, nu utilă.
 * - La adăugare, noul rând intră în vizor cu `scrollIntoView({ block: "nearest" })` — nu sare
 *   pagina la începutul listei.
 */
export default function TabelEditabil<T extends { id: string }>({
  randuri,
  coloane,
  onModifica,
  onAdauga,
  onSterge,
  etichetaAdauga = "+ Adaugă un rând",
  golMesaj = "Niciun rând încă.",
}: Props<T>) {
  const primulCampRefs = useRef(new Map<string, HTMLElement>());
  const lungimeAnterioara = useRef(randuri.length);

  useEffect(() => {
    if (randuri.length > lungimeAnterioara.current) {
      const ultimul = randuri[randuri.length - 1];
      const el = primulCampRefs.current.get(ultimul.id);
      el?.focus();
      el?.scrollIntoView({ block: "nearest" });
    }
    lungimeAnterioara.current = randuri.length;
  }, [randuri]);

  function handleEnter(
    e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>,
    esteUltimulRand: boolean
  ) {
    if (e.key !== "Enter" || e.shiftKey) return;
    if (!esteUltimulRand) return;
    e.preventDefault();
    onAdauga();
  }

  return (
    <div className="flex flex-col gap-2">
      {randuri.length === 0 ? (
        <p className="text-xs text-slate-400">{golMesaj}</p>
      ) : (
        <div className="border border-[#e2e5f0] rounded-lg overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="bg-slate-50 sticky top-0 z-10">
                {coloane.map((c) => (
                  <th
                    key={c.cheie}
                    className={`text-left font-semibold text-[#18257f] px-2 py-1.5 border-b border-[#e2e5f0] ${c.clasa ?? ""}`}
                  >
                    {c.eticheta}
                  </th>
                ))}
                <th className="w-8 border-b border-[#e2e5f0]" />
              </tr>
            </thead>
            <tbody>
              {randuri.map((rand, idx) => {
                const esteUltimulRand = idx === randuri.length - 1;
                return (
                  <tr key={rand.id} className="border-b border-slate-100 last:border-0 align-top">
                    {coloane.map((c, colIdx) => {
                      const valoare = String(rand[c.cheie] ?? "");
                      const setRef = (el: HTMLElement | null) => {
                        if (colIdx !== 0) return;
                        if (el) primulCampRefs.current.set(rand.id, el);
                        else primulCampRefs.current.delete(rand.id);
                      };
                      if (c.tip === "select") {
                        return (
                          <td key={c.cheie} className={`p-1 ${c.clasa ?? ""}`}>
                            <select
                              ref={setRef as React.Ref<HTMLSelectElement>}
                              value={valoare}
                              onChange={(e) => onModifica(rand.id, c.cheie, e.target.value)}
                              className="w-full border-0 bg-transparent text-xs font-semibold text-[#131e66] focus:outline-none focus:ring-1 focus:ring-[#18257f] rounded px-1 py-1"
                            >
                              {(c.optiuni ?? []).map((o) => (
                                <option key={o.valoare} value={o.valoare}>
                                  {o.eticheta}
                                </option>
                              ))}
                            </select>
                          </td>
                        );
                      }
                      if (c.tip === "textarea") {
                        return (
                          <td key={c.cheie} className={`p-1 ${c.clasa ?? ""}`}>
                            <textarea
                              ref={setRef as React.Ref<HTMLTextAreaElement>}
                              value={valoare}
                              onChange={(e) => onModifica(rand.id, c.cheie, e.target.value)}
                              onKeyDown={(e) => handleEnter(e, esteUltimulRand)}
                              placeholder={c.placeholder}
                              rows={2}
                              className="w-full border-0 bg-transparent text-xs resize-y focus:outline-none focus:ring-1 focus:ring-[#18257f] rounded px-1 py-1"
                            />
                          </td>
                        );
                      }
                      return (
                        <td key={c.cheie} className={`p-1 ${c.clasa ?? ""}`}>
                          <input
                            ref={setRef as React.Ref<HTMLInputElement>}
                            type="text"
                            value={valoare}
                            onChange={(e) => onModifica(rand.id, c.cheie, e.target.value)}
                            onKeyDown={(e) => handleEnter(e, esteUltimulRand)}
                            placeholder={c.placeholder}
                            className="w-full border-0 bg-transparent text-xs focus:outline-none focus:ring-1 focus:ring-[#18257f] rounded px-1 py-1"
                          />
                        </td>
                      );
                    })}
                    <td className="p-1 text-center">
                      <button
                        type="button"
                        onClick={() => onSterge(rand.id)}
                        title="Șterge acest rând"
                        className="text-slate-300 hover:text-red-600 px-1"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <button
        type="button"
        onClick={onAdauga}
        className="self-start text-xs font-semibold text-[#18257f] underline"
      >
        {etichetaAdauga}
      </button>
    </div>
  );
}
