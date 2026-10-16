"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "@/lib/auth";
import { poateFolosi, useAcces } from "@/lib/acces";

// `modul` = skill-ul de care ține pagina; meniul arată doar ce permite grupul utilizatorului
const items: { href: string; icon: string; label: string; modul?: string }[] = [
  { href: "/dashboard", icon: "🏠", label: "Acasă" },
  { href: "/minuta", icon: "📝", label: "Minută", modul: "minuta" },
  { href: "/mockup", icon: "🎨", label: "Mockup", modul: "mockup" },
  { href: "/scenarii", icon: "🧪", label: "Scenarii", modul: "scenarii" },
  { href: "/scop-core", icon: "📄", label: "Scop CORE", modul: "scop-core" },
  { href: "/training", icon: "🎓", label: "Training", modul: "training" },
  { href: "/repository", icon: "📁", label: "Repository" },
];

function NavLink({
  href,
  icon,
  label,
  active,
}: {
  href: string;
  icon: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 px-4 py-2.5 text-[13.5px] border-l-4 transition-colors ${
        active
          ? "bg-white/10 text-white border-[#ffd500] font-semibold"
          : "text-[#c7ccf0] border-transparent hover:bg-white/5 hover:text-white"
      }`}
    >
      <span className="text-lg leading-none">{icon}</span>
      <span>{label}</span>
    </Link>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const { acces, eroare } = useAcces();
  // dacă accesul nu poate fi aflat (server pornind), arătăm tot — serverul verifică oricum
  const vizibile = items.filter((it) => !it.modul || !!eroare || poateFolosi(acces, it.modul));

  return (
    <aside className="w-[180px] bg-[#18257f] flex flex-col py-5 shrink-0">
      <Link href="/dashboard" className="px-4 mb-5 block">
        <span className="text-white font-extrabold italic tracking-wide text-[15px]">
          AI&nbsp;Tools
        </span>
        <span className="block h-[3px] w-14 bg-[#ffd500] mt-1" />
      </Link>

      <nav className="flex flex-col">
        {vizibile.map((it) => (
          <NavLink
            key={it.href}
            href={it.href}
            icon={it.icon}
            label={it.label}
            active={pathname === it.href}
          />
        ))}
      </nav>

      <div className="flex-1" />

      {acces?.admin && (
        <NavLink
          href="/grupuri"
          icon="👥"
          label="Grupuri"
          active={pathname === "/grupuri"}
        />
      )}
      <NavLink
        href="/invite"
        icon="👤"
        label="Invită"
        active={pathname === "/invite"}
      />
      <NavLink
        href="/account"
        icon="⚙️"
        label="Cont"
        active={pathname === "/account"}
      />
      <button
        onClick={logout}
        className="flex items-center gap-3 px-4 py-2.5 text-[13.5px] text-[#8a93cf] border-l-4 border-transparent hover:bg-white/5 hover:text-white transition-colors"
      >
        <span className="text-lg leading-none">🚪</span>
        <span>Ieșire</span>
      </button>
    </aside>
  );
}
