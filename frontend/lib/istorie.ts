/**
 * „On this day" din Wikipedia (engleză), pentru ecranul de așteptare.
 *
 * Nu scriem noi istorie: datele vin de la sursă, nu din memoria cuiva. Un
 * singur apel pe zi și pe sesiune, ținut în sessionStorage. Dacă serviciul nu
 * răspunde, secțiunea pur și simplu nu apare — nu blochează nimic.
 */
export type EvenimentIstoric = { an: number; text: string };

const BAZA = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected";

// „Selected" e o listă curatoriată, dar rămâne istorie — iar istoria e plină de
// războaie. Filtrul scoate intrările explicit macabre; nu poate judeca tonul
// unui text, deci nu promitem un ecran numai cu vești bune.
const CUVINTE_GRELE =
  /\b(massacre|genocide|atrocit|beheaded|executed|slaughter|lynch|shot dead|shot and killed|murder|assassinat|rammed|detonat|suicide|torture)/i;

function cheie(luna: number, zi: number): string {
  return `onthisday-en-${luna}-${zi}`;
}

export async function evenimenteleZilei(
  data: Date = new Date()
): Promise<EvenimentIstoric[]> {
  const luna = data.getMonth() + 1;
  const zi = data.getDate();

  try {
    const cache = sessionStorage.getItem(cheie(luna, zi));
    if (cache) return JSON.parse(cache) as EvenimentIstoric[];
  } catch {
    // sessionStorage indisponibil (fereastră privată) — mergem mai departe
  }

  const mm = String(luna).padStart(2, "0");
  const dd = String(zi).padStart(2, "0");

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 6000);
  try {
    const res = await fetch(`${BAZA}/${mm}/${dd}`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return [];
    const data = (await res.json()) as {
      selected?: { year?: number; text?: string }[];
    };

    const toate = (data.selected ?? [])
      .filter((e) => typeof e.text === "string" && typeof e.year === "number")
      .map((e) => ({ an: e.year as number, text: (e.text as string).trim() }));

    const blande = toate.filter((e) => !CUVINTE_GRELE.test(e.text));
    // Dacă filtrul ar goli lista, e mai bine să arătăm istoria așa cum e
    // decât să pretindem că ziua n-a avut nimic.
    const rezultat = blande.length >= 3 ? blande : toate;

    try {
      sessionStorage.setItem(cheie(luna, zi), JSON.stringify(rezultat));
    } catch {
      // fără cache: doar refacem apelul data viitoare
    }
    return rezultat;
  } catch {
    return [];
  } finally {
    clearTimeout(timeout);
  }
}
