"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/auth";

const tools = [
  { href: "/minuta", icon: "📝", label: "Minută" },
  { href: "/mockup", icon: "🎨", label: "Mockup" },
  { href: "/scenarii", icon: "🧪", label: "Scenarii" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-20 min-h-screen bg-slate-100 border-r border-slate-200 flex flex-col items-center py-4 gap-1 shrink-0">
      <div className="text-xs font-bold text-[#1e3a5f] mb-4 text-center leading-tight">
        AI
        <br />
        Tools
      </div>

      {tools.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          className={`w-16 flex flex-col items-center gap-1 py-2 px-1 rounded-lg text-center transition-colors ${
            pathname === t.href
              ? "bg-blue-600 text-white"
              : "text-slate-500 hover:bg-slate-200"
          }`}
        >
          <span className="text-xl">{t.icon}</span>
          <span className="text-[10px] font-semibold">{t.label}</span>
        </Link>
      ))}

      <div className="flex-1" />

      <Link
        href="/repository"
        className={`w-16 flex flex-col items-center gap-1 py-2 px-1 rounded-lg text-center transition-colors ${
          pathname === "/repository"
            ? "bg-blue-600 text-white"
            : "text-slate-500 hover:bg-slate-200"
        }`}
      >
        <span className="text-xl">📁</span>
        <span className="text-[10px] font-semibold">Repository</span>
      </Link>

      <Link
        href="/invite"
        className={`w-16 flex flex-col items-center gap-1 py-2 px-1 rounded-lg text-center transition-colors ${
          pathname === "/invite"
            ? "bg-blue-600 text-white"
            : "text-slate-500 hover:bg-slate-200"
        }`}
      >
        <span className="text-xl">👤</span>
        <span className="text-[10px] font-semibold">Invita</span>
      </Link>

      <button
        onClick={logout}
        className="w-16 flex flex-col items-center gap-1 py-2 px-1 rounded-lg text-center text-slate-400 hover:bg-slate-200 transition-colors mt-1"
      >
        <span className="text-xl">🚪</span>
        <span className="text-[10px]">Ieșire</span>
      </button>
    </aside>
  );
}
