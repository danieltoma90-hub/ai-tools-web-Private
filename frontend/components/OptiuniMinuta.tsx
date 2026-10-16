"use client";

export type OptiuniMinuta = {
  marcaje: boolean;
  limba: "ro" | "en";
  structura: "standard" | "fitgap";
  detaliu: "standard" | "complet";
};

export const OPTIUNI_IMPLICITE: OptiuniMinuta = {
  marcaje: true,
  limba: "ro",
  structura: "standard",
  detaliu: "standard",
};

type Props = {
  value: OptiuniMinuta;
  onChange: (v: OptiuniMinuta) => void;
  /** Free: doar marcajele și limba — structura Fit-Gap și detaliul complet nu încap în cota gratuită. */
  doarDeBaza?: boolean;
  titlu?: string;
};

function Segment<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex rounded-lg border border-slate-200 overflow-hidden w-fit">
      {options.map(([v, label], i) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`px-3 py-1.5 text-xs font-medium transition-colors ${
            i ? "border-l border-slate-200" : ""
          } ${value === v ? "bg-[#18257f] text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** Opțiunile minutei: marcajele pentru revizie, limba, structura (standard sau Fit-Gap) și detaliul. */
export default function OptiuniMinutaPanel({
  value,
  onChange,
  doarDeBaza = false,
  titlu = "Opțiuni minută",
}: Props) {
  const set = (p: Partial<OptiuniMinuta>) => onChange({ ...value, ...p });
  const fitgap = !doarDeBaza && value.structura === "fitgap";
  const lunga = fitgap || (!doarDeBaza && value.detaliu === "complet");

  return (
    <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
      <h3 className="text-sm font-bold text-[#18257f]">{titlu}</h3>

      <label className="flex items-start gap-2 text-sm text-slate-700 cursor-pointer">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={value.marcaje}
          onChange={(e) => set({ marcaje: e.target.checked })}
        />
        <span>
          Marchează pentru revizie ce nu e spus explicit: <b>[DEDUCȚIE]</b>, <b>[COMPLETARE]</b>,{" "}
          <b>[CLARIFICARE NEEDED]</b> (cu ora din înregistrare)
        </span>
      </label>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500">Limba</span>
          <Segment
            value={value.limba}
            options={[
              ["ro", "Română"],
              ["en", "English"],
            ]}
            onChange={(limba) => set({ limba })}
          />
        </div>
        {!doarDeBaza && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Structura</span>
            <Segment
              value={value.structura}
              options={[
                ["standard", "Standard F.05"],
                ["fitgap", "Capitole Fit-Gap"],
              ]}
              onChange={(structura) => set({ structura })}
            />
          </div>
        )}
        {!doarDeBaza && !fitgap && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Detaliu</span>
            <Segment
              value={value.detaliu}
              options={[
                ["standard", "Standard"],
                ["complet", "Complet"],
              ]}
              onChange={(detaliu) => set({ detaliu })}
            />
          </div>
        )}
      </div>

      {fitgap && (
        <p className="text-xs text-slate-500">
          Capitolele unei analize Fit-Gap — rezumat executiv, subiecte cheie, probleme identificate, direcții de
          soluție, acțiuni de urmărire, riscuri și concluzie — pe formatul F.05. Acoperă toată ședința.
        </p>
      )}
      {!fitgap && !doarDeBaza && value.detaliu === "complet" && (
        <p className="text-xs text-slate-500">
          Toată ședința, nu un rezumat: fiecare subiect cu tot ce e tangibil (cifre, exemple, cerințe, decizii).
        </p>
      )}
      {lunga && (
        <p className="text-xs text-amber-700">Minuta completă durează mai mult — câteva minute în plus.</p>
      )}
    </div>
  );
}
