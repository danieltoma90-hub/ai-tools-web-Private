"use client";
import { useEffect, useState } from "react";
import {
  actualizeazaGrup,
  creeazaGrup,
  getConfigAcces,
  seteazaGrupImplicit,
  seteazaMembru,
  stergeGrup,
  type ConfigAcces,
  type Grup,
} from "@/lib/api";

const TOATE = "*";

function formatData(iso: string) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d.getTime())
    ? "—"
    : d.toLocaleString("ro-RO", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Alegerea modulelor unui grup: „toate” (inclusiv cele adăugate ulterior) sau o listă. */
function ModuleAlegere({
  module,
  value,
  onChange,
}: {
  module: Record<string, string>;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const toate = value.includes(TOATE);
  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
        <input type="checkbox" checked={toate} onChange={(e) => onChange(e.target.checked ? [TOATE] : [])} />
        <span>
          <b>Toate modulele</b> <span className="text-slate-500">(și cele adăugate ulterior)</span>
        </span>
      </label>
      <div className="flex flex-wrap gap-x-4 gap-y-1 pl-6">
        {Object.entries(module).map(([id, eticheta]) => (
          <label
            key={id}
            className={`flex items-center gap-1.5 text-sm ${toate ? "text-slate-400" : "text-slate-700 cursor-pointer"}`}
          >
            <input
              type="checkbox"
              disabled={toate}
              checked={toate || value.includes(id)}
              onChange={(e) => onChange(e.target.checked ? [...value, id] : value.filter((m) => m !== id))}
            />
            {eticheta}
          </label>
        ))}
      </div>
    </div>
  );
}

function GrupCard({
  grup,
  module,
  implicit,
  membri,
  ocupat,
  onSalveaza,
  onSterge,
  onImplicit,
}: {
  grup: Grup;
  module: Record<string, string>;
  implicit: boolean;
  membri: number;
  ocupat: boolean;
  onSalveaza: (nume: string, module: string[]) => void;
  onSterge: () => void;
  onImplicit: () => void;
}) {
  const [nume, setNume] = useState(grup.nume);
  const [sel, setSel] = useState<string[]>(grup.module);
  const schimbat = nume.trim() !== grup.nume || [...sel].sort().join() !== [...grup.module].sort().join();

  return (
    <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={nume}
          onChange={(e) => setNume(e.target.value)}
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm font-semibold text-[#18257f] w-64"
        />
        <span className="text-xs text-slate-500">
          {membri} {membri === 1 ? "utilizator" : "utilizatori"}
        </span>
        {implicit ? (
          <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full px-2 py-0.5">
            grup implicit pentru utilizatorii noi
          </span>
        ) : (
          <button onClick={onImplicit} disabled={ocupat} className="text-xs text-[#18257f] underline disabled:opacity-40">
            Fă-l grup implicit
          </button>
        )}
      </div>
      <ModuleAlegere module={module} value={sel} onChange={setSel} />
      <div className="flex gap-2">
        <button
          onClick={() => onSalveaza(nume.trim(), sel)}
          disabled={ocupat || !schimbat || !nume.trim()}
          className="bg-[#18257f] hover:bg-[#131e66] text-white text-xs font-semibold px-3 py-1.5 rounded-lg disabled:opacity-40"
        >
          Salvează
        </button>
        <button
          onClick={onSterge}
          disabled={ocupat || implicit}
          title={implicit ? "Grupul implicit nu se poate șterge" : "Membrii trec în grupul implicit"}
          className="text-xs text-red-700 border border-red-200 px-3 py-1.5 rounded-lg hover:bg-red-50 disabled:opacity-40"
        >
          Șterge grupul
        </button>
      </div>
    </div>
  );
}

/** Administrarea grupurilor de utilizatori și a accesului la module (doar administratori). */
export default function GrupuriPage() {
  const [cfg, setCfg] = useState<ConfigAcces | null>(null);
  const [eroare, setEroare] = useState("");
  const [mesaj, setMesaj] = useState("");
  const [ocupat, setOcupat] = useState(false);
  const [numeNou, setNumeNou] = useState("");
  const [moduleNou, setModuleNou] = useState<string[]>(["minuta"]);

  useEffect(() => {
    getConfigAcces()
      .then(setCfg)
      .catch((e) => setEroare(e instanceof Error ? e.message : "Configurația nu a putut fi citită"));
  }, []);

  async function actiune(fn: () => Promise<unknown>, ok: string) {
    setOcupat(true);
    setEroare("");
    setMesaj("");
    try {
      await fn();
      setCfg(await getConfigAcces());
      setMesaj(ok);
    } catch (e) {
      setEroare(e instanceof Error ? e.message : "Operația a eșuat");
    } finally {
      setOcupat(false);
    }
  }

  const utilizatori = cfg?.utilizatori ?? [];
  const membri = (gid: string) => utilizatori.filter((u) => u.grup === gid).length;

  return (
    <div className="p-6 flex flex-col gap-5 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-[#18257f]">👥 Grupuri de utilizatori</h1>
        <p className="text-sm text-slate-600 mt-1">
          Fiecare utilizator face parte dintr-un grup, iar grupul dă accesul la module. Utilizatorii fără grup ales
          (de exemplu, cei invitați de acum încolo) intră în grupul implicit. Administratorii au acces la tot.
        </p>
      </div>

      {eroare && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{eroare}</div>}
      {mesaj && <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm text-emerald-700">{mesaj}</div>}
      {!cfg && !eroare && <p className="text-sm text-slate-500">Se încarcă grupurile...</p>}

      {cfg && (
        <>
          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-bold text-[#18257f]">Grupuri</h2>
            {cfg.grupuri.map((g) => (
              <GrupCard
                key={`${g.id}|${g.nume}|${g.module.join()}`}
                grup={g}
                module={cfg.module}
                implicit={g.id === cfg.grup_implicit}
                membri={membri(g.id)}
                ocupat={ocupat}
                onSalveaza={(nume, module) => actiune(() => actualizeazaGrup(g.id, nume, module), `Grupul „${nume}” a fost salvat.`)}
                onSterge={() => {
                  if (window.confirm(`Ștergi grupul „${g.nume}”? Membrii lui trec în grupul implicit.`)) {
                    actiune(() => stergeGrup(g.id), `Grupul „${g.nume}” a fost șters.`);
                  }
                }}
                onImplicit={() => actiune(() => seteazaGrupImplicit(g.id), `„${g.nume}” este acum grupul implicit.`)}
              />
            ))}

            <div className="bg-white border border-dashed border-[#c7ccf0] rounded-xl p-4 flex flex-col gap-3">
              <h3 className="text-sm font-bold text-[#18257f]">Grup nou</h3>
              <input
                value={numeNou}
                onChange={(e) => setNumeNou(e.target.value)}
                placeholder="Numele grupului (ex. Consultanți Producție)"
                className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm w-80"
              />
              <ModuleAlegere module={cfg.module} value={moduleNou} onChange={setModuleNou} />
              <button
                onClick={() =>
                  actiune(async () => {
                    await creeazaGrup(numeNou.trim(), moduleNou);
                    setNumeNou("");
                    setModuleNou(["minuta"]);
                  }, `Grupul „${numeNou.trim()}” a fost creat.`)
                }
                disabled={ocupat || !numeNou.trim()}
                className="bg-[#18257f] hover:bg-[#131e66] text-white text-xs font-semibold px-3 py-1.5 rounded-lg w-fit disabled:opacity-40"
              >
                Creează grupul
              </button>
            </div>
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="text-sm font-bold text-[#18257f]">Utilizatori ({utilizatori.length})</h2>
            <div className="bg-white border border-[#e2e5f0] rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[#f2f4fb] text-left text-xs text-slate-600">
                  <tr>
                    <th className="px-4 py-2">Email</th>
                    <th className="px-4 py-2">Stare</th>
                    <th className="px-4 py-2">Ultima conectare</th>
                    <th className="px-4 py-2">Grup</th>
                  </tr>
                </thead>
                <tbody>
                  {utilizatori.map((u) => (
                    <tr key={u.email} className="border-t border-slate-100">
                      <td className="px-4 py-2">
                        {u.email}
                        {u.admin && (
                          <span className="ml-2 text-[11px] bg-[#ffd500]/30 text-[#18257f] rounded-full px-2 py-0.5">
                            admin — acces la tot
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-xs">
                        {u.activ ? (
                          <span className="text-emerald-700">activ</span>
                        ) : (
                          <span className="text-slate-500">invitat, neconectat</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-xs text-slate-500">{formatData(u.ultima_conectare)}</td>
                      <td className="px-4 py-2">
                        <select
                          value={u.grup}
                          disabled={ocupat}
                          onChange={(e) =>
                            actiune(() => seteazaMembru(u.email, e.target.value), `${u.email} a trecut în alt grup.`)
                          }
                          className="border border-slate-200 rounded-lg px-2 py-1 text-sm"
                        >
                          {cfg.grupuri.map((g) => (
                            <option key={g.id} value={g.id}>
                              {g.nume}
                              {!u.explicit && g.id === cfg.grup_implicit ? " (implicit)" : ""}
                            </option>
                          ))}
                        </select>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
