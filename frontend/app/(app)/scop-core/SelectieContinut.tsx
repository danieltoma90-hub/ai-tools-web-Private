"use client";
import type { ScopCoreCatalog, ScopCoreElementCatalog } from "@/lib/api";

type Props = {
  catalog: ScopCoreCatalog | null;
  incarca: boolean;
  eroare: string;
  /** Cheile secțiunilor CORE debifate — ajung în `config.sectiuni_core.fara`. */
  excluse: string[];
  onComutaCore: (cheie: string) => void;
  /** Cheile elementelor adiacente bifate acum (`sursa.cheie` al elementelor suplimentare). */
  bifate: string[];
  /** Pentru fiecare element bifat, clientul variantei alese. */
  variante: Record<string, string>;
  onComutaAdiacent: (el: ScopCoreElementCatalog) => void;
  onSchimbaVarianta: (el: ScopCoreElementCatalog, client: string) => void;
  /** Verticala clientului, sau "" pentru „toate industriile". */
  verticala: string;
  onSchimbaVerticala: (cheie: string) => void;
  /** Arată și modulele propuse în alte industrii decât cea aleasă. */
  aratTot: boolean;
  onComutaAratTot: () => void;
  onBifeazaVerticala: (elemente: ScopCoreElementCatalog[]) => void;
};

/** Ce intră în document: baza CORE și modulele adiacente.
 *
 * Distincția e cea din ofertele noastre. **Baza** e aceeași la toți clienții — se bifează
 * implicit și se debifează doar ce nu se ofertează. **Modulele adiacente** sunt subiectele
 * scrise peste standard la proiectele anterioare; nu se potrivesc tuturor, deci pornesc
 * nebifate și se adaugă unde au obiect, cu textul deja scris atunci.
 *
 * Selectorul de verticală răspunde la întrebarea de dinaintea ofertei: nu „ce am scris
 * vreodată", ci **ce propunem de obicei într-o industrie**. Alegerea unei verticale lasă în
 * listă modulele propuse acolo, marchează cu „2 proiecte" ce s-a repetat (singurul semn
 * obiectiv că modulul ține de industrie, nu de un client anume) și face ca textul implicit al
 * unui modul bifat să fie cel scris în aceeași industrie.
 *
 * Un modul adiacent care stă într-o secțiune CORE debifată nu se poate bifa: documentul l-ar
 * atașa unui capitol care nu există, iar generarea ar cădea cu eroare. Bifa lui se dezactivează,
 * cu motivul la vedere.
 */
export default function SelectieContinut({
  catalog,
  incarca,
  eroare,
  excluse,
  onComutaCore,
  bifate,
  variante,
  onComutaAdiacent,
  onSchimbaVarianta,
  verticala,
  onSchimbaVerticala,
  aratTot,
  onComutaAratTot,
  onBifeazaVerticala,
}: Props) {
  if (incarca) {
    return <p className="text-xs text-slate-500">Se încarcă lista de module…</p>;
  }
  if (eroare || !catalog) {
    return (
      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2">
        {eroare || "Lista de module nu a putut fi încărcată."} Documentul se poate genera și
        așa — intră tot standardul CORE, iar modulele adiacente se adaugă manual mai jos.
      </p>
    );
  }

  const dinVerticala = (el: ScopCoreElementCatalog) =>
    !verticala || el.verticale.includes(verticala);
  const vizibile = catalog.adiacente.filter((el) => aratTot || dinVerticala(el));
  const deBifat = verticala
    ? catalog.adiacente.filter(
        (el) =>
          dinVerticala(el) &&
          !bifate.includes(el.cheie) &&
          !(el.capitol && excluse.includes(el.capitol))
      )
    : [];

  const peCapitol = new Map<string, ScopCoreElementCatalog[]>();
  for (const el of vizibile) {
    const cheie = el.capitol ?? "propriu";
    peCapitol.set(cheie, [...(peCapitol.get(cheie) ?? []), el]);
  }
  const titluCapitol = (cheie: string) =>
    cheie === "propriu"
      ? "Cu subcapitol propriu"
      : catalog.core.find((s) => s.cheie === cheie)?.titlu ?? cheie;

  const grupuri = Array.from(peCapitol.entries()).sort(([a], [b]) =>
    a === "propriu" ? 1 : b === "propriu" ? -1 : titluCapitol(a).localeCompare(titluCapitol(b))
  );

  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Standardul CORE</h3>
        <p className="text-[11px] text-slate-500 mb-2">
          Baza, aceeași la toți clienții. Debifează ce nu se ofertează — secțiunea iese din
          document cu tot ce conține.
        </p>
        <div className="border border-slate-200 rounded-lg divide-y divide-slate-100">
          {catalog.core.map((s) => {
            const inclusa = !excluse.includes(s.cheie);
            return (
              <label
                key={s.cheie}
                className="flex items-start gap-2 px-3 py-2 cursor-pointer hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  checked={inclusa}
                  onChange={() => onComutaCore(s.cheie)}
                  className="mt-0.5 accent-[#18257f]"
                />
                <span className="flex-1">
                  <span
                    className={`block text-xs font-medium ${
                      inclusa ? "text-slate-800" : "text-slate-400 line-through"
                    }`}
                  >
                    {s.titlu}
                  </span>
                  <span className="block text-[11px] text-slate-400">
                    {s.fluxuri} fluxuri · {s.puncte} puncte de detaliere
                  </span>
                </span>
              </label>
            );
          })}
        </div>
        <p className="text-[11px] text-slate-500 mt-2">
          {catalog.core.length - excluse.length} din {catalog.core.length} secțiuni incluse
        </p>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-1">Module adiacente</h3>
        <p className="text-[11px] text-slate-500 mb-2">
          Scrise la proiectele anterioare. Bifează ce intră la clientul ăsta — textul și
          fluxurile vin de acolo și rămân editabile mai jos.
        </p>

        <div className="flex flex-wrap items-center gap-2 mb-2">
          <label className="text-[11px] font-semibold text-slate-500">Industria clientului:</label>
          <select
            value={verticala}
            onChange={(e) => onSchimbaVerticala(e.target.value)}
            className="border border-slate-300 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
          >
            <option value="">Toate industriile ({catalog.adiacente.length} module)</option>
            {catalog.verticale.map((v) => (
              <option key={v.cheie} value={v.cheie}>
                {v.nume} — {v.module} module, {v.proiecte}{" "}
                {v.proiecte === 1 ? "proiect" : "proiecte"}
              </option>
            ))}
          </select>
        </div>

        {verticala && (
          <div className="text-[11px] text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 mb-2 flex flex-col gap-1">
            <span>
              Ce am propus la{" "}
              <strong>
                {catalog.verticale.find((v) => v.cheie === verticala)?.nume ?? verticala}
              </strong>
              : {catalog.adiacente.filter(dinVerticala).length} module, la{" "}
              {catalog.verticale.find((v) => v.cheie === verticala)?.clienti.join(", ")}.
            </span>
            <span className="flex flex-wrap items-center gap-3">
              {deBifat.length > 0 && (
                <button
                  type="button"
                  onClick={() => onBifeazaVerticala(deBifat)}
                  className="font-semibold text-[#18257f] underline"
                >
                  Bifează-le pe toate ({deBifat.length})
                </button>
              )}
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={aratTot}
                  onChange={onComutaAratTot}
                  className="accent-[#18257f]"
                />
                arată și modulele din alte industrii
              </label>
            </span>
          </div>
        )}

        <div className="border border-slate-200 rounded-lg divide-y divide-slate-100 max-h-[28rem] overflow-y-auto">
          {grupuri.length === 0 && (
            <p className="px-3 py-3 text-[11px] text-slate-500">
              Niciun modul propus încă la industria asta. Bifează „arată și modulele din alte
              industrii” sau scrie-l ca secțiune nouă mai jos.
            </p>
          )}
          {grupuri.map(([cheie, elemente]) => {
            const capitolExclus = cheie !== "propriu" && excluse.includes(cheie);
            return (
              <div key={cheie}>
                <p className="px-3 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                  {titluCapitol(cheie)}
                  {capitolExclus && " — secțiune debifată"}
                </p>
                {elemente.map((el) => {
                  const esteBifat = bifate.includes(el.cheie);
                  const clientAles =
                    variante[el.cheie] ??
                    el.variante.find((v) => verticala && v.vertical === verticala)?.client ??
                    el.variante[0]?.client ??
                    "";
                  const repetari = verticala ? el.proiecte_pe_verticala[verticala] ?? 0 : 0;
                  const dinAlta = Boolean(verticala) && !dinVerticala(el);
                  return (
                    <div key={el.cheie} className="px-3 pb-2">
                      <label
                        className={`flex items-start gap-2 ${
                          capitolExclus ? "opacity-40" : "cursor-pointer"
                        }`}
                        title={
                          capitolExclus
                            ? "Secțiunea CORE în care intră e debifată — bifeaz-o întâi."
                            : undefined
                        }
                      >
                        <input
                          type="checkbox"
                          checked={esteBifat}
                          disabled={capitolExclus}
                          onChange={() => onComutaAdiacent(el)}
                          className="mt-0.5 accent-[#18257f]"
                        />
                        <span className="flex-1">
                          <span className="flex items-center gap-1.5">
                            <span className="text-xs font-medium text-slate-800">
                              {el.denumire}
                            </span>
                            {repetari > 1 && (
                              <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded px-1">
                                {repetari} proiecte
                              </span>
                            )}
                            {dinAlta && (
                              <span className="text-[10px] text-slate-500 bg-slate-100 border border-slate-200 rounded px-1">
                                altă industrie
                              </span>
                            )}
                          </span>
                          <span className="block text-[11px] text-slate-400">
                            {el.variante[0]?.fluxuri.length
                              ? `${el.variante[0].fluxuri.length} fluxuri · `
                              : ""}
                            livrat la {el.clienti.join(", ") || "—"}
                          </span>
                        </span>
                      </label>
                      {esteBifat && el.variante.length > 1 && (
                        <div className="flex items-center gap-2 mt-1 ml-6">
                          <span className="text-[11px] text-slate-500">Textul de la:</span>
                          <select
                            value={clientAles}
                            onChange={(e) => onSchimbaVarianta(el, e.target.value)}
                            className="border border-slate-300 rounded px-1.5 py-0.5 text-[11px] focus:outline-none focus:ring-2 focus:ring-[#18257f]"
                          >
                            {el.variante.map((v) => (
                              <option key={v.client} value={v.client}>
                                {v.client}
                                {verticala && v.vertical === verticala
                                  ? " — aceeași industrie"
                                  : ""}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        <p className="text-[11px] text-slate-500 mt-2">
          {bifate.length} din {catalog.adiacente.length} module adiacente bifate
        </p>
      </div>
    </div>
  );
}
