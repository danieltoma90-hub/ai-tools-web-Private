"use client";
import { useEffect, useState } from "react";
import { getDocuments } from "@/lib/api";

type Doc = {
  name: string;
  tool: string;
  storage_path: string;
  created_at: string;
  size: number;
  download_url: string;
};

const TOOL_ICONS: Record<string, string> = {
  minuta: "📝",
  mockup: "🎨",
  scenarii: "🧪",
};
const TOOL_LABELS: Record<string, string> = {
  minuta: "Minută",
  mockup: "Mockup",
  scenarii: "Scenarii",
};

function formatBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function RepositoryPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("toate");

  useEffect(() => {
    getDocuments()
      .then(setDocs)
      .finally(() => setLoading(false));
  }, []);

  const filtered =
    filter === "toate" ? docs : docs.filter((d) => d.tool === filter);

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#1e3a5f]">📁 Repository</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Toate documentele generate de echipă
          </p>
        </div>
        <div className="flex gap-2">
          {["toate", "minuta", "mockup", "scenarii"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filter === f
                  ? "bg-blue-600 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {f === "toate"
                ? "Toate"
                : `${TOOL_ICONS[f]} ${TOOL_LABELS[f]}`}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="text-sm text-slate-400">Se încarcă...</p>}

      {!loading && filtered.length === 0 && (
        <p className="text-sm text-slate-400">
          Niciun document generat încă.
        </p>
      )}

      {!loading && filtered.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">
                  Tip
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">
                  Nume fișier
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">
                  Data
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">
                  Mărime
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500">
                  Acțiuni
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((doc) => {
                return (
                  <tr key={doc.storage_path ?? doc.name} className="hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <span className="text-base" title={TOOL_LABELS[doc.tool] ?? doc.tool}>
                        {TOOL_ICONS[doc.tool] ?? "📄"}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-medium text-[#1e3a5f] max-w-xs truncate">
                      {doc.name}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">
                      {formatDate(doc.created_at)}
                    </td>
                    <td className="px-4 py-3 text-slate-400 text-xs">
                      {formatBytes(doc.size)}
                    </td>
                    <td className="px-4 py-3">
                      <a
                        href={doc.download_url}
                        target="_blank"
                        rel="noreferrer"
                        className="bg-blue-50 text-blue-600 text-xs px-2.5 py-1 rounded font-medium hover:bg-blue-100"
                      >
                        ↓ Descarcă
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
