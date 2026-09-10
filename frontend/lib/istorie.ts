/**
 * Evenimentele importante ale zilei, pentru ecranul de așteptare.
 *
 * Selecția o face serverul — Claude alege ce a schimbat lumea din lista
 * Wikipedia a zilei, iar rezultatul e ținut permanent, fiindcă istoria nu se
 * schimbă. Aici vine gata aleasă: ~1KB în loc de cei 146KB ai feed-ului brut.
 *
 * Dacă nu răspunde, secțiunea pur și simplu nu apare — nu blochează nimic.
 */
import { getIstoriaZilei } from "./api";

export type EvenimentIstoric = { an: number; text: string };

function cheie(data: Date): string {
  return `onthisday-${data.getMonth() + 1}-${data.getDate()}-v3`;
}

export async function evenimenteleZilei(
  data: Date = new Date()
): Promise<EvenimentIstoric[]> {
  try {
    const cache = sessionStorage.getItem(cheie(data));
    if (cache) return JSON.parse(cache) as EvenimentIstoric[];
  } catch {
    // sessionStorage indisponibil (fereastră privată) — mergem mai departe
  }

  try {
    const { evenimente } = await getIstoriaZilei();
    try {
      sessionStorage.setItem(cheie(data), JSON.stringify(evenimente));
    } catch {
      // fără cache local: doar refacem cererea la următoarea sesiune
    }
    return evenimente;
  } catch {
    return [];
  }
}
