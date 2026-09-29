// Tipurile rândurilor editabile din modul „document” — fiecare are un `id` local (generat în
// browser, nu ajunge niciodată la backend), folosit ca `key` React și pentru reordonare/ștergere.

export type SuplimentarUI = {
  id: string;
  titlu: string;
  intro: string;
  /** Un punct pe linie — convertit în listă la trimitere. */
  puncte: string;
  nota: string;
  /** "propriu" (subcapitol propriu în cap. 4) sau cheia unei secțiuni CORE. */
  plasare: string;
};

export type CerintaUI = {
  id: string;
  zona: string;
  cerinta: string;
  raspuns: string;
  incadrare: "A" | "P" | "D" | "N";
};

export type DelimitareRandUI = {
  id: string;
  zona: string;
  tratat_in: string;
  interfatare: string;
};

export type FluxRandUI = {
  id: string;
  etapa: string;
  ce_se_intampla: string;
  rezultat: string;
};
