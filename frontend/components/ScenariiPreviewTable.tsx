"use client";
import type { Scenariu } from "@/lib/api";

const PRIORITY_STYLES: Record<string, string> = {
  Critical: "bg-red-100 text-red-700",
  High: "bg-orange-100 text-orange-700",
  Medium: "bg-yellow-100 text-yellow-700",
  Low: "bg-slate-100 text-slate-600",
};

export default function ScenariiPreviewTable({ scenarios }: { scenarios: Scenariu[] }) {
  const stubCount = scenarios.filter((s) => !s.ai).length;
  return (
    <div className="flex flex-col gap-2">
      {stubCount > 0 && stubCount < scenarios.length && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {stubCount} scenarii marcate cu galben au fost generate fără AI
          (apelul AI a eșuat pentru modulul respectiv) — conțin pași generici.
        </p>
      )}
      <div className="overflow-auto max-h-96 border border-slate-200 rounded-lg">
        <table className="w-full text-xs">
          <thead className="bg-slate-800 text-white sticky top-0">
            <tr>
              <th className="px-2 py-2 text-left font-semibold">ID</th>
              <th className="px-2 py-2 text-left font-semibold">Capitol</th>
              <th className="px-2 py-2 text-left font-semibold">Titlu Scenariu</th>
              <th className="px-2 py-2 text-left font-semibold">Tip</th>
              <th className="px-2 py-2 text-left font-semibold">Prioritate</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr
                key={s.id}
                className={`border-t border-slate-100 ${s.ai ? "" : "bg-amber-50"}`}
                title={`${s.obiectiv}\n\nPași:\n${s.pasi}`}
              >
                <td className="px-2 py-1.5 font-mono whitespace-nowrap">{s.id}</td>
                <td className="px-2 py-1.5">{s.capitol}</td>
                <td className="px-2 py-1.5">{s.titlu_scenariu}</td>
                <td className="px-2 py-1.5 whitespace-nowrap">{s.tip_test}</td>
                <td className="px-2 py-1.5">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      PRIORITY_STYLES[s.prioritate] ?? "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {s.prioritate}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-400">
        {scenarios.length} scenarii · treci cu mouse-ul peste un rând pentru obiectiv și pași.
      </p>
    </div>
  );
}
