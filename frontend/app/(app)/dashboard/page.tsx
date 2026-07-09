"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getDocuments, getStorageUsage } from "@/lib/api";

type Doc = {
  name: string;
  tool: string;
  owner: string;
  created_at: string;
  size: number;
  download_url: string;
};

const TOOLS = [
  {
    href: "/minuta",
    tool: "minuta",
    icon: "📝",
    title: "Minută",
    desc: "Transcript Teams (.vtt / .docx) → minută F.05 formatată, cu pași următori.",
  },
  {
    href: "/mockup",
    tool: "mockup",
    icon: "🎨",
    title: "Mockup",
    desc: "Excel ecran Charisma → document Word cu zone, butoane și coloane.",
  },
  {
    href: "/scenarii",
    tool: "scenarii",
    icon: "🧪",
    title: "Scenarii",
    desc: "Specificație → scenarii de testare Excel, gata de import.",
  },
];

const TOOL_ICONS: Record<string, string> = {
  minuta: "📝",
  mockup: "🎨",
  scenarii: "🧪",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export default function Dashboard() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [usage, setUsage] = useState<{ percent: number } | null>(null);

  useEffect(() => {
    getDocuments().then(setDocs).catch(() => {});
    getStorageUsage().then(setUsage).catch(() => {});
  }, []);

  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const recentCount = docs.filter(
    (d) => d.created_at && new Date(d.created_at).getTime() > weekAgo
  ).length;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="bg-[#343a8c] text-white rounded-xl px-6 py-5 mb-5">
        <h1 className="text-lg font-bold mb-1">Bună! 👋</h1>
        <p className="text-[13px] text-[#d5d8f5]">
          {docs.length} documente în Repository
          {recentCount > 0 && ` · ${recentCount} generate săptămâna aceasta`}
          {usage && ` · spațiu ocupat ${usage.percent}%`}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        {TOOLS.map((t) => (
          <div
            key={t.tool}
            className="bg-white rounded-xl border border-[#e2e5f0] p-4"
          >
            <span className="inline-block bg-[#18257f] text-white rounded-lg px-3 py-1.5 text-[13px] font-bold mb-2">
              {t.icon} {t.title}
            </span>
            <p className="text-xs text-slate-500 mb-3 min-h-[34px] leading-relaxed">
              {t.desc}
            </p>
            <div className="flex gap-2">
              <Link
                href={t.href}
                className="bg-[#18257f] hover:bg-[#131e66] text-white rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors"
              >
                Generează
              </Link>
              <Link
                href={`/repository?tool=${t.tool}`}
                className="border border-[#d6d9e2] text-[#18257f] hover:bg-[#f1f3f8] rounded-lg px-3.5 py-1.5 text-xs font-semibold transition-colors"
              >
                Istoric
              </Link>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-[#e2e5f0] p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold text-[#18257f]">
            📁 Ultimele documente
          </h2>
          <Link
            href="/repository"
            className="text-xs font-semibold text-[#18257f] hover:underline"
          >
            Vezi tot Repository →
          </Link>
        </div>
        {docs.length === 0 && (
          <p className="text-xs text-slate-400">Niciun document generat încă.</p>
        )}
        <ul className="divide-y divide-slate-100">
          {docs.slice(0, 5).map((d) => (
            <li
              key={`${d.tool}/${d.owner}/${d.name}`}
              className="flex items-center gap-3 py-2 text-[13px]"
            >
              <span>{TOOL_ICONS[d.tool] ?? "📄"}</span>
              <span className="flex-1 truncate font-medium text-[#1e3a5f]">
                {d.name}
              </span>
              <span className="text-xs text-slate-400 hidden sm:block">
                {d.owner}
              </span>
              <span className="text-xs text-slate-400 tabular-nums">
                {formatDate(d.created_at)}
              </span>
              <a
                href={d.download_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-semibold text-[#18257f] hover:underline"
              >
                ↓ Descarcă
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
