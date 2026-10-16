"use client";
import { usePathname } from "next/navigation";
import { MODULE_ETICHETE, MODUL_RUTA, poateFolosi, useAcces } from "@/lib/acces";

/** Paginile unui modul pe care grupul utilizatorului nu îl include arată un mesaj în locul tool-ului.
 *  Serverul refuză oricum cererile (403); aici doar nu lăsăm pe cineva să completeze un formular degeaba. */
export default function AccesGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { acces, eroare } = useAcces();
  const modul = MODUL_RUTA[pathname];
  const doarAdmin = pathname === "/grupuri";

  // pagină comună, sau accesul nu poate fi aflat acum (serverul pornește) — serverul verifică oricum
  if ((!modul && !doarAdmin) || eroare) return <>{children}</>;
  if (!acces) return <div className="p-6 text-sm text-slate-500">Se verifică accesul...</div>;
  if (doarAdmin ? acces.admin : poateFolosi(acces, modul)) return <>{children}</>;

  return (
    <div className="p-6">
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 text-sm text-amber-800 max-w-xl">
        <p className="font-semibold mb-1">Nu ai acces la această pagină</p>
        <p>
          Grupul tău, <b>{acces.grup.nume}</b>, nu include{" "}
          {doarAdmin ? "administrarea grupurilor" : `modulul „${MODULE_ETICHETE[modul] ?? modul}”`}. Cere acces
          administratorului.
        </p>
      </div>
    </div>
  );
}
