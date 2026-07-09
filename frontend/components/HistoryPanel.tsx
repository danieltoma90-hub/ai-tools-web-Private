"use client";
import { useEffect, useState } from "react";
import { getDocuments } from "@/lib/api";

type Doc = {
  name: string;
  created_at: string;
  size: number;
  download_url: string;
};

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function HistoryPanel({ refreshKey }: { refreshKey: number }) {
  const [docs, setDocs] = useState<Doc[]>([]);

  useEffect(() => {
    getDocuments()
      .then((d) => setDocs(d.slice(0, 5)))
      .catch(() => {});
  }, [refreshKey]);

  return (
    <aside className="w-[120px] shrink-0 border-l border-slate-200 bg-slate-50 p-3 overflow-y-auto">
      <p className="text-[9px] font-bold text-slate-400 uppercase tracking-wide mb-3">
        Recent
      </p>
      {docs.length === 0 && (
        <p className="text-[10px] text-slate-400">Niciun fișier generat</p>
      )}
      {docs.map((doc) => (
        <div
          key={doc.name}
          className="mb-3 border-b border-slate-200 pb-2 last:border-0"
        >
          <p className="text-[9px] font-semibold text-[#1e3a5f] truncate">
            {doc.name}
          </p>
          <p className="text-[8px] text-slate-400 mb-1">
            {formatDate(doc.created_at)}
          </p>
          <a
            href={doc.download_url}
            target="_blank"
            rel="noreferrer"
            className="inline-block bg-[#eef0f8] text-[#18257f] text-[8px] px-1.5 py-0.5 rounded"
          >
            ↓ descarcă
          </a>
        </div>
      ))}
    </aside>
  );
}
