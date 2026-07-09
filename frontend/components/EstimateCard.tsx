"use client";
import type { EstimateResponse } from "@/lib/api";

type Props = {
  estimate: EstimateResponse;
  toolLabel: string; // "scenariile" | "documentația"
  onAi: () => void;
  onNoAi: () => void;
  onCancel: () => void;
};

export default function EstimateCard({ estimate, toolLabel, onAi, onNoAi, onCancel }: Props) {
  const tokens = estimate.est_tokens.toLocaleString("ro-RO");
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-col gap-4">
      <div>
        <h3 className="text-sm font-semibold text-slate-800 mb-1">
          Estimare procesare cu AI
        </h3>
        <p className="text-sm text-slate-600">
          ~{tokens} tokeni · ~{estimate.est_minutes} min
          {estimate.calls ? ` · ${estimate.calls} ${estimate.calls === 1 ? "apel" : "apeluri"} AI` : ""}
          {estimate.modules ? ` · ${estimate.modules} module` : ""}
        </p>
      </div>

      {!estimate.fits_budget && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Cota gratuită zilnică de AI e aproape epuizată pentru acest fișier.
          Poți continua fără AI acum sau poți reveni mâine pentru varianta AI.
        </p>
      )}

      <div className="flex flex-col gap-2">
        <button
          onClick={onAi}
          disabled={!estimate.fits_budget}
          className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ✨ Generează cu AI
        </button>
        <button
          onClick={onNoAi}
          className="w-full bg-slate-100 text-slate-700 py-2.5 rounded-lg text-sm font-semibold hover:bg-slate-200"
        >
          Continuă fără AI (instant, {toolLabel} standard)
        </button>
        <button onClick={onCancel} className="text-sm text-slate-500 underline">
          Anulează
        </button>
      </div>
    </div>
  );
}
