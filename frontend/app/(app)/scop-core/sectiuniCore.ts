// Cele zece secțiuni standard Charisma ERP CORE (`charisma_core.SECTIUNI` din backend) —
// singura sursă de chei valide pentru `in_modul` / `sectiuni_core` / `ordine_cap4`.
// Etichetele sunt titlurile reale ale secțiunilor, ca utilizatorul să recunoască imediat modulul.
export type SectiuneCore = { cheie: string; titlu: string };

export const SECTIUNI_CORE: SectiuneCore[] = [
  { cheie: "configurare", titlu: "Configurare inițială a sistemului" },
  { cheie: "nomenclatoare", titlu: "Modul General — Nomenclatoare și structuri de bază" },
  { cheie: "contabilitate", titlu: "Modulul Contabilitate" },
  { cheie: "financiar", titlu: "Modulul Financiar" },
  { cheie: "vanzari", titlu: "Modulul Vânzări" },
  { cheie: "achizitii", titlu: "Modulul Achiziții" },
  { cheie: "mijloace-fixe", titlu: "Modulul Mijloace Fixe" },
  { cheie: "stocuri", titlu: "Modulul Gestiunea Stocurilor" },
  { cheie: "analiza", titlu: "Analiza multidimensională" },
  { cheie: "migrare", titlu: "Migrarea și inițializarea datelor" },
];

export function titluSectiune(cheie: string): string {
  return SECTIUNI_CORE.find((s) => s.cheie === cheie)?.titlu ?? cheie;
}
