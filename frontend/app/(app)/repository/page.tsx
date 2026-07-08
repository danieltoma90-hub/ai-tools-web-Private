"use client";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getDocuments, deleteDocument, getStorageUsage } from "@/lib/api";

type Doc = {
  name: string;
  tool: string;
  owner: string;
  storage_path: string;
  created_at: string;
  size: number;
  download_url: string;
};

type Usage = { used_bytes: number; quota_bytes: number; percent: number };

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

const ALERT_THRESHOLD = 95; // % — alerta rosie + sugestii de curatenie
const WARN_THRESHOLD = 80; // % — bara devine portocalie
const OLD_FILE_DAYS = 60;

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

/** Numele de baza, fara sufixul _YYYYMMDD_HHMMSS pus de generatoare. */
function stemOf(name: string): string {
  return name.replace(/_\d{8}_\d{6}(?=\.\w+$)/, "");
}

type Suggestion = { doc: Doc; reason: string };

/** Candidati la stergere: versiuni vechi ale aceluiasi document + fisiere vechi. */
function cleanupSuggestions(docs: Doc[]): Suggestion[] {
  const suggestions: Suggestion[] = [];
  const suggested = new Set<string>();

  const groups = new Map<string, Doc[]>();
  for (const d of docs) {
    const key = `${d.tool}|${stemOf(d.name)}`;
    groups.set(key, [...(groups.get(key) ?? []), d]);
  }
  for (const list of groups.values()) {
    if (list.length < 2) continue;
    const sorted = [...list].sort((a, b) =>
      b.created_at.localeCompare(a.created_at)
    );
    for (const old of sorted.slice(1)) {
      suggestions.push({
        doc: old,
        reason: `Versiune veche — există una mai nouă din ${formatDate(sorted[0].created_at)}`,
      });
      suggested.add(old.storage_path);
    }
  }

  const cutoff = Date.now() - OLD_FILE_DAYS * 24 * 3600 * 1000;
  for (const d of docs) {
    if (suggested.has(d.storage_path)) continue;
    if (d.created_at && new Date(d.created_at).getTime() < cutoff) {
      suggestions.push({
        doc: d,
        reason: `Document vechi — creat acum peste ${OLD_FILE_DAYS} de zile`,
      });
    }
  }

  return suggestions.sort((a, b) => b.doc.size - a.doc.size);
}

export default function RepositoryPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("toate");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);

  const refreshUsage = useCallback(() => {
    getStorageUsage().then(setUsage).catch(() => {});
  }, []);

  useEffect(() => {
    getDocuments()
      .then(setDocs)
      .finally(() => setLoading(false));
    refreshUsage();
  }, [refreshUsage]);

  const suggestions = useMemo(() => cleanupSuggestions(docs), [docs]);
  const overThreshold = (usage?.percent ?? 0) >= ALERT_THRESHOLD;
  const suggestionsVisible = showSuggestions || overThreshold;
  const recoverable = suggestions.reduce((s, x) => s + x.doc.size, 0);

  async function handleDelete(doc: Doc) {
    if (
      !window.confirm(
        `Ștergi definitiv „${doc.name}”?\nAcțiunea nu poate fi anulată.`
      )
    )
      return;
    setDeleting(doc.storage_path);
    setError("");
    try {
      await deleteDocument(doc.storage_path);
      setDocs((prev) => prev.filter((d) => d.storage_path !== doc.storage_path));
      refreshUsage();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ștergerea a eșuat");
    } finally {
      setDeleting(null);
    }
  }

  const filtered =
    filter === "toate" ? docs : docs.filter((d) => d.tool === filter);

  const barColor = overThreshold
    ? "bg-red-500"
    : (usage?.percent ?? 0) >= WARN_THRESHOLD
      ? "bg-amber-500"
      : "bg-blue-500";

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
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
              {f === "toate" ? "Toate" : `${TOOL_ICONS[f]} ${TOOL_LABELS[f]}`}
            </button>
          ))}
        </div>
      </div>

      {usage && (
        <div className="mb-4">
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span>
              Spațiu ocupat: {formatBytes(usage.used_bytes)} /{" "}
              {formatBytes(usage.quota_bytes)} ({usage.percent}%)
            </span>
            {suggestions.length > 0 && (
              <button
                onClick={() => setShowSuggestions((v) => !v)}
                className="text-blue-600 hover:underline"
              >
                🧹 Sugestii curățenie ({suggestions.length})
              </button>
            )}
          </div>
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${barColor}`}
              style={{ width: `${Math.min(usage.percent, 100)}%` }}
            />
          </div>
        </div>
      )}

      {overThreshold && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          ⚠️ <strong>Spațiul de stocare a atins {usage?.percent}%.</strong>{" "}
          Ștergeți documente pentru a putea genera altele noi — mai jos sunt
          propuse fișierele cele mai sigure de șters.
        </div>
      )}

      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {suggestionsVisible && suggestions.length > 0 && (
        <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-semibold text-amber-800">
              🧹 Propuneri de ștergere — se pot elibera ~
              {formatBytes(recoverable)}
            </p>
            {!overThreshold && (
              <button
                onClick={() => setShowSuggestions(false)}
                className="text-xs text-amber-700 hover:underline"
              >
                Ascunde
              </button>
            )}
          </div>
          <p className="text-xs text-amber-700 mb-3">
            Criterii: versiuni mai vechi ale aceluiași document și fișiere
            create acum peste {OLD_FILE_DAYS} de zile. Verificați înainte de
            ștergere.
          </p>
          <ul className="space-y-1.5">
            {suggestions.map(({ doc, reason }) => (
              <li
                key={doc.storage_path}
                className="flex items-center justify-between gap-3 text-xs bg-white rounded px-3 py-2 border border-amber-100"
              >
                <span className="truncate">
                  <span className="mr-1">{TOOL_ICONS[doc.tool] ?? "📄"}</span>
                  <span className="font-medium text-[#1e3a5f]">{doc.name}</span>
                  <span className="text-slate-400">
                    {" "}
                    · {formatBytes(doc.size)} · {reason}
                  </span>
                </span>
                <button
                  onClick={() => handleDelete(doc)}
                  disabled={deleting === doc.storage_path}
                  className="shrink-0 bg-red-50 text-red-600 px-2.5 py-1 rounded font-medium hover:bg-red-100 disabled:opacity-40"
                >
                  {deleting === doc.storage_path ? "..." : "🗑 Șterge"}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {loading && <p className="text-sm text-slate-400">Se încarcă...</p>}

      {!loading && filtered.length === 0 && (
        <p className="text-sm text-slate-400">Niciun document generat încă.</p>
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
              {filtered.map((doc) => (
                <tr key={doc.storage_path ?? doc.name} className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <span
                      className="text-base"
                      title={TOOL_LABELS[doc.tool] ?? doc.tool}
                    >
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
                    <div className="flex items-center gap-2">
                      <a
                        href={doc.download_url}
                        target="_blank"
                        rel="noreferrer"
                        className="bg-blue-50 text-blue-600 text-xs px-2.5 py-1 rounded font-medium hover:bg-blue-100"
                      >
                        ↓ Descarcă
                      </a>
                      <button
                        onClick={() => handleDelete(doc)}
                        disabled={deleting === doc.storage_path}
                        className="bg-red-50 text-red-600 text-xs px-2.5 py-1 rounded font-medium hover:bg-red-100 disabled:opacity-40"
                        title="Șterge documentul"
                      >
                        {deleting === doc.storage_path ? "..." : "🗑 Șterge"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
