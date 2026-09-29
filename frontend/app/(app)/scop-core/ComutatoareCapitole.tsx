"use client";

export type CheieCapitol =
  | "context"
  | "abordare"
  | "beneficii"
  | "acoperire"
  | "delimitare"
  | "premise"
  | "confirmari"
  | "sinteza"
  | "validare";

const ETICHETE: { cheie: CheieCapitol; titlu: string }[] = [
  { cheie: "context", titlu: "Contextul proiectului" },
  { cheie: "abordare", titlu: "Abordarea și metodologia de implementare" },
  { cheie: "beneficii", titlu: "Beneficiile soluției" },
  { cheie: "acoperire", titlu: "Analiza de acoperire a cerințelor" },
  { cheie: "delimitare", titlu: "Delimitarea față de documentul-frate" },
  { cheie: "premise", titlu: "Premise și responsabilități" },
  { cheie: "confirmari", titlu: "Puncte de confirmat înainte de validarea scopului" },
  { cheie: "sinteza", titlu: "Sinteza scopului funcțional" },
  { cheie: "validare", titlu: "Validarea scopului" },
];

type Props = {
  valori: Record<CheieCapitol, boolean>;
  /** Cheile din listă sunt needitabile — motivul apare ca notă sub comutator. Folosit pentru
   * capitolele pe care ecranul curent nu are cum să le umple cu conținut real: activarea lor
   * ar scrie doar marcaje „[ de completat ]” într-o ofertă către client. */
  blocate: Partial<Record<CheieCapitol, string>>;
  onSchimba: (cheie: CheieCapitol, valoare: boolean) => void;
};

/** Cele nouă comutatoare din `config.capitole`. */
export default function ComutatoareCapitole({ valori, blocate, onSchimba }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5">
      {ETICHETE.map(({ cheie, titlu }) => {
        const motivBlocare = blocate[cheie];
        const activ = valori[cheie];
        return (
          <label
            key={cheie}
            className={`flex items-start gap-2.5 ${motivBlocare ? "cursor-default" : "cursor-pointer"}`}
          >
            <input
              type="checkbox"
              checked={activ}
              disabled={!!motivBlocare}
              onChange={(e) => onSchimba(cheie, e.target.checked)}
              className="mt-0.5 w-4 h-4 accent-[#18257f] disabled:opacity-40"
            />
            <span className="text-sm">
              <span className={activ ? "text-[#18257f] font-medium" : "text-slate-500"}>
                {titlu}
              </span>
              {motivBlocare && (
                <span className="block text-[11px] text-slate-400 mt-0.5">{motivBlocare}</span>
              )}
            </span>
          </label>
        );
      })}
    </div>
  );
}
