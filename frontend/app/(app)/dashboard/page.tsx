"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { getDashboardSummary, type DashboardSummary } from "@/lib/api";

const CACHE_KEY = "dashboard-summary-v1";

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
    desc: "Specificație → catalog standard + cerințe specifice client, în Excel.",
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
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    // 1) pictura instant din cache-ul sesiunii (stale-while-revalidate)
    try {
      const cached = sessionStorage.getItem(CACHE_KEY);
      if (cached) {
        setData(JSON.parse(cached) as DashboardSummary);
        setStale(true);
      }
    } catch {
      // cache corupt — il ignoram
    }
    // 2) datele proaspete, intr-un singur apel
    getDashboardSummary()
      .then((fresh) => {
        setData(fresh);
        setStale(false);
        try {
          sessionStorage.setItem(CACHE_KEY, JSON.stringify(fresh));
        } catch {
          // storage plin — nu blocam pagina
        }
      })
      .catch(() => setStale(false));
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="bg-[#343a8c] text-white rounded-xl px-6 py-5 mb-5">
        <h1 className="text-lg font-bold mb-1">Bună! 👋</h1>
        <p className="text-[13px] text-[#d5d8f5]">
          {data ? (
            <>
              {data.total_documents} documente în Repository
              {data.week_count > 0 && ` · ${data.week_count} generate săptămâna aceasta`}
              {` · spațiu ocupat ${data.usage.percent}%`}
              {stale && " · se actualizează..."}
            </>
          ) : (
            "Se încarcă statisticile... (prima cerere trezește serverul, ~20s)"
          )}
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
        {!data && (
          <p className="text-xs text-slate-400">Se încarcă...</p>
        )}
        {data && data.documents.length === 0 && (
          <p className="text-xs text-slate-400">Niciun document generat încă.</p>
        )}
        {data && (
          <ul className="divide-y divide-slate-100">
            {data.documents.map((d) => (
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
        )}
      </div>
    </div>
  );
}
