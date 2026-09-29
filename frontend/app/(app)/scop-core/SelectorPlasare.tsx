"use client";
import type { SectiuneCore } from "./sectiuniCore";

type Props = {
  valoare: string; // "propriu" | cheia unei secțiuni din `sectiuniIncluse`
  onChange: (valoare: string) => void;
  /** Doar secțiunile CORE incluse efectiv în document — backend-ul respinge (422) un
   * element suplimentar atașat unui modul exclus, așa că lista nu oferă niciodată o opțiune
   * care ar produce acea eroare. */
  sectiuniIncluse: SectiuneCore[];
  className?: string;
};

/** Alegerea plasării unui element suplimentar: în interiorul unui modul CORE, sau capitol
 * propriu în capitolul 4. */
export default function SelectorPlasare({ valoare, onChange, sectiuniIncluse, className }: Props) {
  return (
    <select
      value={valoare}
      onChange={(e) => onChange(e.target.value)}
      className={
        className ??
        "border border-[#8a93cf] bg-[#eef0f8] text-[#131e66] rounded-lg px-2 py-1.5 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-[#18257f]"
      }
    >
      <option value="propriu">Subcapitol propriu</option>
      {sectiuniIncluse.map((s) => (
        <option key={s.cheie} value={s.cheie}>
          În interiorul: {s.titlu}
        </option>
      ))}
    </select>
  );
}
