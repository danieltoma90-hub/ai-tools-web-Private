/**
 * „On this day" din Wikipedia (engleză), pentru ecranul de așteptare.
 *
 * Nu scriem noi istorie: datele vin de la sursă, nu din memoria cuiva. Un
 * singur apel pe zi și pe sesiune, ținut în sessionStorage. Dacă serviciul nu
 * răspunde, secțiunea pur și simplu nu apare — nu blochează nimic.
 *
 * Din lista zilei păstrăm doar evenimentele care au mutat ceva la scara lumii,
 * bune sau rele: tratate, revoluții, descoperiri, catastrofe. Fără nașteri,
 * fără decese, fără sport, fără fapt divers. Selecția se face pe cuvinte-cheie
 * ponderate — e o aproximare, nu o judecată, și se mai strecoară prin ea și
 * evenimente mărunte.
 */
export type EvenimentIstoric = { an: number; text: string };

const BAZA = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected";

// Afară: nașteri, decese, sport, divertisment, fapt divers, accidente.
const EXCLUSE =
  /\b(was born|were born|\bb\.\s*\d{4}|died|death of|funeral|football|soccer|baseball|basketball|cricket|olympic|championship|tournament|scored|album|single|song|film|television|episode|comic|video game|nightclub|robbery|kidnapp|asteroid|comet|frigate|police raid|boarded and captured|flight \d|airliner|airlines|aircraft crashed|plane crashed|derailed)/i;

// Semne că evenimentul a schimbat lumea, nu doar ziua.
const PUTERNICE =
  /\b(world war|treaty of|peace treaty|armistice|declared independence|independence from|constitution|revolution|abolish|emancipat|universal suffrage|civil rights|apartheid|holocaust|genocide|first human|first person to|first successful|first flight|moon|spacecraft|space station|orbit the earth|vaccine|pandemic|smallpox|penicillin|atomic bomb|nuclear weapon|hydrogen bomb|united nations|european union|nato|league of nations|world wide web|the internet|printing press|partition of|dissolution of|fall of|collapse of)/gi;

const MEDII =
  /\b(treaty|surrender|liberated|annexed|occupation|coup|overthrew|founded|established|ratified|signed into law|proclaimed|elected president|dictator|regime|discovered|invented|patented|launched|satellite|reactor|earthquake|tsunami|eruption|famine|epidemic|terrorist attack|massacre|civil war|republic of|kingdom of)/gi;

const PRAG = 2;
const MAX_EVENIMENTE = 8;

function scor(text: string): number {
  if (EXCLUSE.test(text)) return -1;
  const unice = (re: RegExp) =>
    new Set(Array.from(text.matchAll(re), (m) => m[0].toLowerCase())).size;
  return unice(PUTERNICE) * 2 + unice(MEDII);
}

function cheie(luna: number, zi: number): string {
  return `onthisday-en-${luna}-${zi}-v2`;
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
    const payload = (await res.json()) as {
      selected?: { year?: number; text?: string }[];
    };

    const cotate = (payload.selected ?? [])
      .filter((e) => typeof e.text === "string" && typeof e.year === "number")
      .map((e) => {
        const text = (e.text as string).trim();
        return { an: e.year as number, text, scor: scor(text) };
      })
      .sort((a, b) => b.scor - a.scor);

    // Zilele slabe există: mai bine coborâm pragul decât să nu arătăm nimic.
    let alese = cotate.filter((e) => e.scor >= PRAG);
    if (alese.length < 3) alese = cotate.filter((e) => e.scor >= 1);

    const rezultat = alese
      .slice(0, MAX_EVENIMENTE)
      .map(({ an, text }) => ({ an, text }));

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
