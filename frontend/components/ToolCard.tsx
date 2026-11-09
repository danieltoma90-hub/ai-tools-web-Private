"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getRecentDocuments, type Doc } from "@/lib/api";

type Props = {
  icon: string;
  title: string;
  description: string;
  /** Când e dat, sub titlu apar ultimele documente ale tool-ului și drumul spre Istoric. */
  tool?: string;
  /** Se schimbă după fiecare document generat, ca lista să se reîncarce. */
  recentKey?: number;
};

function data(iso: string) {
  return new Date(iso).toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const RECENTE = 3;

export default function ToolCard({ icon, title, description, tool, recentKey = 0 }: Props) {
  const [docs, setDocs] = useState<Doc[] | null>(null);

  useEffect(() => {
    if (!tool) return;
    // Doar documentele tool-ului curent, doar câte se afișează: altfel fiecare
    // intrare pe pagină ar lista și semna tot depozitul ca să arate trei.
    getRecentDocuments(tool, RECENTE)
      .then(setDocs)
      .catch(() => setDocs([]));
  }, [tool, recentKey]);

  return (
    <div className="mb-4 pb-4 border-b border-slate-200">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-[#eef0f8] rounded-lg flex items-center justify-center text-xl shrink-0">
          {icon}
        </div>
        <div>
          <h2 className="font-bold text-[#1e3a5f] text-base">{title}</h2>
          <p className="text-xs text-slate-500">{description}</p>
        </div>
      </div>

      {tool && docs && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-slate-500 font-medium">
            {docs.length ? "Recent:" : "Niciun document generat încă."}
          </span>
          {docs.map((doc) => (
            <a
              key={doc.name}
              href={doc.download_url}
              target="_blank"
              rel="noreferrer"
              title={`Descarcă ${doc.name}`}
              className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1 hover:border-[#18257f] hover:bg-[#eef0f8] transition-colors max-w-[280px]"
            >
              <span className="truncate text-[#1e3a5f]">{doc.name}</span>
              <span className="text-slate-400 shrink-0 tabular-nums">{data(doc.created_at)}</span>
              <span className="text-[#18257f] shrink-0" aria-hidden>
                ↓
              </span>
            </a>
          ))}
          <Link href={`/repository?tool=${tool}`} className="text-[#18257f] hover:underline font-medium">
            Toate în Istoric →
          </Link>
        </div>
      )}
    </div>
  );
}
