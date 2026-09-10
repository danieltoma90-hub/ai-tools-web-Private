/**
 * Progresul unui job, calculat din pașii reali raportați de server.
 *
 * Regula: bara nu trece niciodată de capătul etapei curente fără un semnal
 * real. Înăuntrul unei etape se apropie asimptotic de capăt, fără să-l atingă.
 * O bară care ajunge la 95% și stă acolo e mai rea decât nicio bară.
 */

export type Etapa = {
  /** Identificatorul pasului trimis de server ("metadata", "chunk", ...). */
  id: string;
  /** Cât din durata totală ocupă etapa, relativ la celelalte. */
  pondere: number;
  /** Cât durează de obicei — folosit doar pentru mișcarea din interiorul etapei. */
  secundeTipice: number;
};

/** Pașii de forma "chunk:3/8" spun exact cât s-a făcut. */
function fractieRaportata(step: string): number | null {
  const m = step.match(/:(\d+)\/(\d+)$/);
  if (!m) return null;
  const facut = Number(m[1]);
  const total = Number(m[2]);
  if (!total || total < facut) return null;
  return facut / total;
}

function idPas(step: string): string {
  return step.split(":")[0];
}

/** Se apropie de 1 fără să ajungă: 63% la durata tipică, 86% la dublul ei. */
function asimptotic(secunde: number, tipice: number): number {
  if (tipice <= 0) return 0;
  return Math.min(0.92, 1 - Math.exp(-secunde / tipice));
}

/**
 * Procentul (0–1) pentru pasul curent.
 *
 * `step` null înseamnă că jobul abia a pornit și n-a raportat încă nimic.
 */
export function calculeazaProgres(
  etape: Etapa[],
  step: string | null,
  secundeInEtapa: number
): number {
  if (!etape.length) return 0;
  const total = etape.reduce((s, e) => s + e.pondere, 0);

  let idx = step ? etape.findIndex((e) => e.id === idPas(step)) : 0;
  if (idx < 0) idx = 0; // pas necunoscut: rămânem unde suntem, nu sărim înainte

  const inainte = etape.slice(0, idx).reduce((s, e) => s + e.pondere, 0);
  const etapa = etape[idx];
  const fractie =
    (step ? fractieRaportata(step) : null) ??
    asimptotic(secundeInEtapa, etapa.secundeTipice);

  return (inainte + etapa.pondere * fractie) / total;
}

// Ponderile vin din felul în care lucrează fiecare pipeline, nu din estimări
// rotunde: la minuta free cea mai mare parte a timpului se duce pe bucățile de
// transcript, la mockup pe apelul AI, la training pe citirea specificației.
export const ETAPE_MINUTA_AI: Etapa[] = [
  { id: "extrageri", pondere: 0.85, secundeTipice: 35 },
  { id: "building", pondere: 0.15, secundeTipice: 4 },
];

export const ETAPE_MINUTA_FREE: Etapa[] = [
  { id: "metadata", pondere: 0.12, secundeTipice: 12 },
  { id: "chunk", pondere: 0.58, secundeTipice: 90 },
  { id: "synthesis", pondere: 0.2, secundeTipice: 25 },
  { id: "building", pondere: 0.1, secundeTipice: 4 },
];

export const ETAPE_SCENARII: Etapa[] = [
  { id: "parsing", pondere: 0.15, secundeTipice: 20 },
  { id: "gen", pondere: 0.6, secundeTipice: 120 },
  { id: "deps", pondere: 0.15, secundeTipice: 25 },
  { id: "building", pondere: 0.1, secundeTipice: 5 },
];

export const ETAPE_MOCKUP: Etapa[] = [
  { id: "parsing", pondere: 0.2, secundeTipice: 5 },
  { id: "ai", pondere: 0.65, secundeTipice: 40 },
  { id: "building", pondere: 0.15, secundeTipice: 5 },
];

export const ETAPE_TRAINING: Etapa[] = [
  { id: "catalog", pondere: 0.05, secundeTipice: 2 },
  { id: "specificatie", pondere: 0.6, secundeTipice: 30 },
  { id: "planificare", pondere: 0.05, secundeTipice: 2 },
  { id: "documente", pondere: 0.3, secundeTipice: 5 },
];
