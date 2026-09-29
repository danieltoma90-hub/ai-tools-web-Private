"use client";

export type OrdineItem =
  | { tip: "sectiune"; id: string }
  | { tip: "propriu"; id: string };

type Props = {
  items: OrdineItem[];
  /** Eticheta afișată pentru un item — titlul secțiunii CORE, sau titlul curent al
   * elementului suplimentar cu subcapitol propriu. */
  eticheta: (item: OrdineItem) => string;
  onMuta: (index: number, delta: -1 | 1) => void;
};

/**
 * Ordinea subcapitolelor capitolului 4 — derivată automat din secțiunile CORE incluse și din
 * elementele suplimentare cu „subcapitol propriu” (vezi `DocumentModeForm`), niciodată tastată
 * liber: lista mereu conține exact ce trebuie, fără ca utilizatorul să poată uita un element sau
 * scrie o cheie necunoscută — exact cele două greșeli pe care backend-ul le respinge cu 422.
 * Utilizatorul poate doar reordona, cu săgeți sus/jos (accesibile de la tastatură, fără drag&drop).
 */
export default function OrdineCap4({ items, eticheta, onMuta }: Props) {
  if (items.length === 0) {
    return (
      <p className="text-xs text-slate-400">
        Nimic de ordonat încă — activează cel puțin o secțiune sau un element suplimentar.
      </p>
    );
  }
  return (
    <ol className="flex flex-col gap-1">
      {items.map((item, idx) => (
        <li
          key={`${item.tip}:${item.id}`}
          className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5"
        >
          <span className="text-xs text-slate-400 w-5 shrink-0 text-right">{idx + 1}.</span>
          <span className="text-xs text-[#131e66] flex-1 truncate">{eticheta(item)}</span>
          <button
            type="button"
            onClick={() => onMuta(idx, -1)}
            disabled={idx === 0}
            title="Mută mai sus"
            className="text-slate-400 hover:text-[#18257f] disabled:opacity-20 disabled:hover:text-slate-400 px-1"
          >
            ↑
          </button>
          <button
            type="button"
            onClick={() => onMuta(idx, 1)}
            disabled={idx === items.length - 1}
            title="Mută mai jos"
            className="text-slate-400 hover:text-[#18257f] disabled:opacity-20 disabled:hover:text-slate-400 px-1"
          >
            ↓
          </button>
        </li>
      ))}
    </ol>
  );
}
