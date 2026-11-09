"use client";
import { useEffect, useState } from "react";
import { getConsum, type SumarConsum } from "@/lib/api";

const MODULE: Record<string, string> = {
  minuta: "Minută",
  mockup: "Mockup",
  scenarii: "Scenarii",
  "scop-core": "Scop CORE",
  training: "Training",
  diagnostic: "Verifică acum",
  "on-this-day": "On this day",
};

const PERIOADE = [7, 30, 90];

function usd(n: number): string {
  return `$${n.toFixed(n < 1 ? 3 : 2)}`;
}

function mii(n: number): string {
  return n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
}

function cand(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? iso
    : d.toLocaleString("ro-RO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/**
 * Cât a costat fiecare generare, adunat pe modul și pe coleg. Costul e estimat din
 * tokenii raportați de Claude și prețurile publice; factura exactă e în consola Anthropic.
 */
export default function ConsumClaude() {
  const [zile, setZile] = useState(30);
  const [date, setDate] = useState<SumarConsum | null>(null);
  const [eroare, setEroare] = useState("");

  useEffect(() => {
    let viu = true;
    getConsum(zile)
      .then((d) => {
        if (!viu) return;
        setDate(d);
        setEroare("");
      })
      .catch((e) => viu && setEroare(e instanceof Error ? e.message : "Consumul nu a putut fi citit"));
    return () => {
      viu = false;
    };
  }, [zile]);

  const t = date?.total;
  const cacheProcent =
    t && t.intrare + t.cache_citit > 0 ? Math.round((t.cache_citit / (t.intrare + t.cache_citit)) * 100) : 0;

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-sm font-bold text-[#18257f]">Consum Claude</h2>
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs">
          {PERIOADE.map((p) => (
            <button
              key={p}
              onClick={() => setZile(p)}
              className={`px-2.5 py-1 ${zile === p ? "bg-[#18257f] text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              {p} zile
            </button>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-500">
        Cost estimat din tokenii raportați de Claude, la prețurile publice ale modelului. Factura
        exactă e în consola Anthropic, la Usage.
      </p>

      {eroare && <p className="text-xs text-red-700">{eroare}</p>}

      {date && t && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3">
              <p className="text-xl font-bold text-[#18257f] tabular-nums">{usd(t.cost_usd)}</p>
              <p className="text-[11px] text-slate-500">în ultimele {date.zile} zile</p>
            </div>
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3">
              <p className="text-xl font-bold text-[#18257f] tabular-nums">{t.generari}</p>
              <p className="text-[11px] text-slate-500">generări cu Claude</p>
            </div>
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3">
              <p className="text-xl font-bold text-[#18257f] tabular-nums">
                {t.generari ? usd(t.cost_usd / t.generari) : "—"}
              </p>
              <p className="text-[11px] text-slate-500">cost mediu pe generare</p>
            </div>
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3">
              <p className="text-xl font-bold text-[#18257f] tabular-nums">{cacheProcent}%</p>
              <p className="text-[11px] text-slate-500">din intrare citită din cache</p>
            </div>
          </div>

          {t.generari === 0 ? (
            <p className="text-xs text-slate-500">Nicio generare cu Claude în această perioadă.</p>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <TabelSumar
                titlu="Pe modul"
                randuri={date.pe_modul.map((r) => ({ ...r, nume: MODULE[r.modul] ?? r.modul }))}
              />
              <TabelSumar titlu="Pe coleg" randuri={date.pe_utilizator.map((r) => ({ ...r, nume: r.email }))} />
            </div>
          )}

          {date.recente.length > 0 && (
            <details className="bg-white border border-[#e2e5f0] rounded-xl">
              <summary className="px-4 py-2 text-xs font-semibold text-[#18257f] cursor-pointer">
                Ultimele {date.recente.length} generări, una câte una
              </summary>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-[#f2f4fb] text-left text-slate-600">
                    <tr>
                      <th className="px-3 py-2">Când</th>
                      <th className="px-3 py-2">Modul</th>
                      <th className="px-3 py-2">Coleg</th>
                      <th className="px-3 py-2">Efort</th>
                      <th className="px-3 py-2 text-right">Intrare / cache / ieșire</th>
                      <th className="px-3 py-2 text-right">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {date.recente.map((g, k) => (
                      <tr key={`${g.cand}-${k}`} className="border-t border-slate-100">
                        <td className="px-3 py-1.5 text-slate-500 whitespace-nowrap">{cand(g.cand)}</td>
                        <td className="px-3 py-1.5 whitespace-nowrap">
                          {MODULE[g.modul] ?? g.modul}
                          {!g.reusit && <span className="ml-1 text-red-600">(eșuat)</span>}
                        </td>
                        <td className="px-3 py-1.5">{g.email}</td>
                        <td className="px-3 py-1.5">{g.efort}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums text-slate-600 whitespace-nowrap">
                          {mii(g.intrare + g.cache_scris)} / {mii(g.cache_citit)} / {mii(g.iesire)}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{usd(g.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
        </>
      )}
    </section>
  );
}

function TabelSumar({
  titlu,
  randuri,
}: {
  titlu: string;
  randuri: { nume: string; generari: number; cost_usd: number; cost_mediu_usd: number }[];
}) {
  return (
    <div className="bg-white border border-[#e2e5f0] rounded-xl overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="bg-[#f2f4fb] text-left text-slate-600">
          <tr>
            <th className="px-3 py-2">{titlu}</th>
            <th className="px-3 py-2 text-right">Generări</th>
            <th className="px-3 py-2 text-right">Medie</th>
            <th className="px-3 py-2 text-right">Total</th>
          </tr>
        </thead>
        <tbody>
          {randuri.map((r) => (
            <tr key={r.nume} className="border-t border-slate-100">
              <td className="px-3 py-1.5 truncate max-w-[200px]">{r.nume}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{r.generari}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{usd(r.cost_mediu_usd)}</td>
              <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{usd(r.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
