"use client";
import { useRef, useState } from "react";
import UploadZone from "@/components/UploadZone";
import ProcessingSpinner from "@/components/ProcessingSpinner";
import {
  uploadSourceFile,
  postScopCoreGenereazaDocument,
  getScopCoreJob,
  type ScopCoreDocConfig,
  type ScopCoreDocContinut,
  type ScopCoreDocumentSummary,
} from "@/lib/api";
import { isColdStartError, pollJob } from "@/lib/poll";
import { SECTIUNI_CORE, titluSectiune } from "./sectiuniCore";
import ComutatoareCapitole, { type CheieCapitol } from "./ComutatoareCapitole";
import TabelEditabil, { type ColoanaTabel } from "./TabelEditabil";
import OrdineCap4, { type OrdineItem } from "./OrdineCap4";
import SectiuneSuplimentaraCard from "./SectiuneSuplimentaraCard";
import type { SuplimentarUI, CerintaUI, DelimitareRandUI, FluxRandUI } from "./tipuri";

type State = "idle" | "processing" | "done" | "error";
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

const OPTIUNI_INCADRARE: ColoanaTabel<CerintaUI>["optiuni"] = [
  { valoare: "A", eticheta: "A — Acoperit" },
  { valoare: "P", eticheta: "P — Parțial" },
  { valoare: "D", eticheta: "D — De definit" },
  { valoare: "N", eticheta: "N — În afara scopului" },
];

/** Împarte un text pe linii, curățat de spații și de liniile goale — folosit pentru liste
 * scurte (entități, puncte) unde un rând per intrare e mai simplu decât un editor de etichete. */
function randuriDinText(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

function descarca(b64: string, filename: string) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes]));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * Modul „Document complet (11 capitole)”. Spre deosebire de modul „capitol”, generarea rulează
 * sincron pe server — un 422 din cele două erori deliberate ale lui `scope.genereaza` (element
 * atașat unui modul exclus; ordinea capitolului 4 incompletă) ar veni direct din apelul POST, nu
 * dintr-un job eșuat mai târziu. Ecranul le evită STRUCTURAL, nu doar le raportează:
 *  - `SelectorPlasare` oferă doar modulele CORE incluse efectiv (aici, mereu toate zece — nu
 *    există comutator de excludere a unui modul întreg în acest ecran);
 *  - `ordine_cap4` nu se scrie niciodată de mână — se derivă automat din secțiunile incluse și
 *    din elementele cu „subcapitol propriu” (vezi efectul de reconciliere de mai jos), deci e
 *    mereu completă și fără chei necunoscute.
 */
export default function DocumentModeForm({ onGenerated }: { onGenerated: () => void }) {
  // --- Clientul ------------------------------------------------------------------------
  const [nume, setNume] = useState("");
  const [numeComplet, setNumeComplet] = useState("");
  const [domeniu, setDomeniu] = useState("");
  const [entitatiText, setEntitatiText] = useState("");
  const [observatii, setObservatii] = useState("");

  // --- Documentul gazdă (opțional) -----------------------------------------------------
  const [gazdaFile, setGazdaFile] = useState<File | null>(null);

  // --- Referirea la documentul de Producție --------------------------------------------
  const [frateTitlu, setFrateTitlu] = useState("");
  const [frateArie, setFrateArie] = useState("");
  const [delimitareRows, setDelimitareRows] = useState<DelimitareRandUI[]>([]);

  // --- Secțiunile adăugate peste standard -----------------------------------------------
  const [suplimentare, setSuplimentare] = useState<SuplimentarUI[]>([]);
  const [ordine, setOrdine] = useState<OrdineItem[]>(
    SECTIUNI_CORE.map((s) => ({ tip: "sectiune" as const, id: s.cheie }))
  );
  // Semnătura seturilor pe care se bazează `ordine` (secțiuni CORE incluse — mereu toate zece
  // aici — plus id-urile elementelor cu subcapitol propriu). Când diferă de ultima procesată,
  // se reconciliază ACUM, în timpul randării (pattern-ul React recomandat pentru „ajustează
  // starea când se schimbă o intrare” — vezi https://react.dev/learn/you-might-not-need-an-effect),
  // nu într-un `useEffect`: un `setState` direct în efect ar declanșa un randare în cascadă.
  const [ordineDinSemnal, setOrdineDinSemnal] = useState<string>(
    SECTIUNI_CORE.map((s) => `sectiune:${s.cheie}`).join("|")
  );

  // --- Matricea de acoperire + fluxul operațional ---------------------------------------
  const [acoperireRows, setAcoperireRows] = useState<CerintaUI[]>([]);
  const [fluxRows, setFluxRows] = useState<FluxRandUI[]>([]);

  // --- Comutatoarele editabile ale capitolelor (restul se derivă din conținut) ---------
  const [capitoleManual, setCapitoleManual] = useState({
    context: true,
    abordare: true,
    premise: true,
    sinteza: true,
    validare: true,
  });

  // --- Forma capitolului 6 + diacritice --------------------------------------------------
  const [formaAcoperire, setFormaAcoperire] = useState<"apdn" | "trei-grupe">("apdn");
  const [faraDiacritice, setFaraDiacritice] = useState(false);

  // --- Stare ecran -----------------------------------------------------------------------
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState("");
  /** Eroare de validare (422) legată de conținutul formularului — afișată lângă butonul de
   * generare, nu ca un banner general la eroare: utilizatorul rămâne pe formular și o poate
   * corecta imediat. */
  const [formError, setFormError] = useState("");
  const [progress, setProgress] = useState("Se inițializează...");
  const [step, setStep] = useState<string | null>(null);
  const [result, setResult] = useState<{
    filename: string;
    docxB64: string;
    summary: ScopCoreDocumentSummary | null;
  } | null>(null);
  const cancelledRef = useRef(false);
  const idRef = useRef(0);
  const formErrorRef = useRef<HTMLDivElement>(null);

  function idNou(): string {
    idRef.current += 1;
    return `d-${idRef.current}`;
  }

  // Reconciliază automat ordinea capitolului 4: păstrează ordinea aleasă de utilizator pentru
  // ce rămâne, adaugă la final ce-i nou (o secțiune CORE mereu există; un element suplimentar
  // nou cu subcapitol propriu), elimină ce a dispărut (elementul a fost șters sau mutat
  // „în interiorul modulului X”). Lista trimisă la generare e mereu completă — niciodată
  // incompletă sau cu chei necunoscute, cele două condiții pe care backend-ul le respinge.
  const propriiIds = suplimentare.filter((s) => s.plasare === "propriu").map((s) => s.id);
  const semnalCurent = [
    ...SECTIUNI_CORE.map((s) => `sectiune:${s.cheie}`),
    ...propriiIds.map((id) => `propriu:${id}`),
  ].join("|");
  if (semnalCurent !== ordineDinSemnal) {
    setOrdineDinSemnal(semnalCurent);
    const dorite = new Set(semnalCurent.split("|"));
    const pastrate = ordine.filter((o) => dorite.has(`${o.tip}:${o.id}`));
    const prezente = new Set(pastrate.map((o) => `${o.tip}:${o.id}`));
    const adaugate: OrdineItem[] = [];
    for (const s of SECTIUNI_CORE) {
      if (!prezente.has(`sectiune:${s.cheie}`)) adaugate.push({ tip: "sectiune", id: s.cheie });
    }
    for (const id of propriiIds) {
      if (!prezente.has(`propriu:${id}`)) adaugate.push({ tip: "propriu", id });
    }
    setOrdine([...pastrate, ...adaugate]);
  }

  function mutaOrdine(index: number, delta: -1 | 1) {
    setOrdine((prev) => {
      const j = index + delta;
      if (j < 0 || j >= prev.length) return prev;
      const nou = [...prev];
      [nou[index], nou[j]] = [nou[j], nou[index]];
      return nou;
    });
  }

  function etichetaOrdine(item: OrdineItem): string {
    if (item.tip === "sectiune") return titluSectiune(item.id);
    const el = suplimentare.find((s) => s.id === item.id);
    const titlu = el?.titlu.trim();
    return titlu ? titlu : "(secțiune fără titlu — nu va apărea în document)";
  }

  // --- Elemente suplimentare ---------------------------------------------------------------
  function adaugaSuplimentar() {
    setSuplimentare((els) => [
      ...els,
      { id: idNou(), titlu: "", intro: "", puncte: "", nota: "", plasare: "propriu" },
    ]);
  }
  function modificaSuplimentar(id: string, patch: Partial<SuplimentarUI>) {
    setSuplimentare((els) => els.map((el) => (el.id === id ? { ...el, ...patch } : el)));
  }
  function stergeSuplimentar(id: string) {
    setSuplimentare((els) => els.filter((el) => el.id !== id));
  }

  const titluriProprii = suplimentare
    .filter((s) => s.plasare === "propriu")
    .map((s) => s.titlu.trim())
    .filter(Boolean);
  const titluriDuplicate = Array.from(
    new Set(titluriProprii.filter((t, i) => titluriProprii.indexOf(t) !== i))
  );

  // --- Delimitare (tabel) --------------------------------------------------------------
  function adaugaDelimitare() {
    setDelimitareRows((rs) => [...rs, { id: idNou(), zona: "", tratat_in: "", interfatare: "" }]);
  }
  function modificaDelimitare(id: string, cheie: keyof DelimitareRandUI, valoare: string) {
    setDelimitareRows((rs) => rs.map((r) => (r.id === id ? { ...r, [cheie]: valoare } : r)));
  }
  function stergeDelimitare(id: string) {
    setDelimitareRows((rs) => rs.filter((r) => r.id !== id));
  }

  // --- Matricea de acoperire (tabel) -----------------------------------------------------
  function adaugaCerinta() {
    setAcoperireRows((rs) => [
      ...rs,
      { id: idNou(), zona: "", cerinta: "", raspuns: "", incadrare: "A" },
    ]);
  }
  function modificaCerinta(id: string, cheie: keyof CerintaUI, valoare: string) {
    setAcoperireRows((rs) =>
      rs.map((r) => {
        if (r.id !== id) return r;
        if (cheie === "incadrare") return { ...r, incadrare: valoare as CerintaUI["incadrare"] };
        return { ...r, [cheie]: valoare };
      })
    );
  }
  function stergeCerinta(id: string) {
    setAcoperireRows((rs) => rs.filter((r) => r.id !== id));
  }
  const numarPeIncadrare = { A: 0, P: 0, D: 0, N: 0 };
  for (const r of acoperireRows) numarPeIncadrare[r.incadrare] += 1;

  // --- Fluxul operațional (tabel) --------------------------------------------------------
  function adaugaFlux() {
    setFluxRows((rs) => [...rs, { id: idNou(), etapa: "", ce_se_intampla: "", rezultat: "" }]);
  }
  function modificaFlux(id: string, cheie: keyof FluxRandUI, valoare: string) {
    setFluxRows((rs) => rs.map((r) => (r.id === id ? { ...r, [cheie]: valoare } : r)));
  }
  function stergeFlux(id: string) {
    setFluxRows((rs) => rs.filter((r) => r.id !== id));
  }

  // --- Derivate ----------------------------------------------------------------------------
  const frateExista = frateTitlu.trim().length > 0;
  // Delimitarea are conținut fillable din acest ecran doar dacă titlul documentului-frate E
  // completat ȘI există cel puțin un rând — fără rânduri, `_cap_delimitare` ar scrie un tabel
  // cu un singur rând placeholder, exact ce trebuie evitat.
  const capitoleEfective: Record<CheieCapitol, boolean> = {
    ...capitoleManual,
    acoperire: acoperireRows.length > 0,
    delimitare: frateExista && delimitareRows.length > 0,
    beneficii: false,
    confirmari: false,
  };
  const blocateCapitole: Partial<Record<CheieCapitol, string>> = {
    acoperire:
      acoperireRows.length > 0
        ? `Activ automat — matricea de acoperire are ${acoperireRows.length} cerință(e).`
        : "Se activează automat când adaugi cel puțin o cerință în matricea de acoperire, mai jos.",
    delimitare: !frateExista
      ? "Se activează automat când completezi titlul documentului de Producție, mai jos."
      : delimitareRows.length === 0
        ? "Completează cel puțin un rând de delimitare mai jos ca să activezi acest capitol."
        : `Activ automat — ${delimitareRows.length} rând(uri) de delimitare completate.`,
    beneficii: "Fără interfață pentru conținutul acestei liste în acest ecran — dezactivat.",
    confirmari: "Fără interfață pentru conținutul acestei liste în acest ecran — dezactivat.",
  };

  const potGenera = nume.trim().length > 0 && state !== "processing";

  function construiesteCerere(): { config: ScopCoreDocConfig; continut: ScopCoreDocContinut } {
    const titluriPropriiById = new Map(suplimentare.map((s) => [s.id, s.titlu.trim()]));
    const ordineCap4 = ordine
      .map((o) => (o.tip === "sectiune" ? o.id : titluriPropriiById.get(o.id) ?? ""))
      .filter(Boolean);

    const config: ScopCoreDocConfig = {
      client: {
        nume: nume.trim(),
        nume_complet: numeComplet.trim(),
        domeniu: domeniu.trim(),
        entitati: randuriDinText(entitatiText),
        observatii: observatii.trim(),
      },
      // Obiect gol, intenționat: acest ecran nu are câmpuri pentru titlu/subtitlu/versiune/
      // elaborat_de/furnizor — o cheie goală face ca `scope.genereaza` să-și folosească propriile
      // implicite (`d.get("titlu", "Descrierea soluției ofertate")` etc.). Dacă am trimite aici
      // șiruri goale explicite, `.get()` le-ar întoarce PE ELE, nu valorile implicite, iar
      // coperta documentului ar ieși cu titlul gol.
      document: {} as ScopCoreDocConfig["document"],
      document_frate: {
        exista: frateExista,
        titlu: frateTitlu.trim(),
        arie_acoperita: frateArie.trim(),
        coduri: [],
      },
      sectiuni_core: { toate: true, doar: [], fara: [] },
      capitole: capitoleEfective,
      stil: {
        document_gazda: "",
        antet: "",
        forma_acoperire: formaAcoperire,
        fara_diacritice: faraDiacritice,
      },
    };

    const continut: ScopCoreDocContinut = {
      client: {
        nume: nume.trim(),
        nume_complet: numeComplet.trim(),
        domeniu: domeniu.trim(),
        entitati: randuriDinText(entitatiText),
        observatii: observatii.trim(),
        situatie_actuala: [],
        obiective: [],
      },
      suplimentare: suplimentare
        .filter((s) => s.titlu.trim())
        .map((s) => ({
          titlu: s.titlu.trim(),
          intro: s.intro.trim(),
          puncte: randuriDinText(s.puncte),
          fluxuri: [],
          nota: s.nota.trim(),
          in_modul: s.plasare === "propriu" ? null : s.plasare,
        })),
      acoperire: acoperireRows
        .filter((r) => r.cerinta.trim() && r.raspuns.trim())
        .map((r) => ({
          zona: r.zona.trim(),
          cerinta: r.cerinta.trim(),
          raspuns: r.raspuns.trim(),
          incadrare: r.incadrare,
        })),
      delimitare: delimitareRows
        .filter((r) => r.zona.trim() && r.tratat_in.trim() && r.interfatare.trim())
        .map((r) => ({
          zona: r.zona.trim(),
          tratat_in: r.tratat_in.trim(),
          interfatare: r.interfatare.trim(),
        })),
      flux_operational: fluxRows
        .filter((r) => r.etapa.trim() && r.ce_se_intampla.trim() && r.rezultat.trim())
        .map((r) => ({
          etapa: r.etapa.trim(),
          ce_se_intampla: r.ce_se_intampla.trim(),
          rezultat: r.rezultat.trim(),
        })),
      ordine_cap4: ordineCap4,
      beneficii: [],
      confirmari: [],
    };
    return { config, continut };
  }

  async function handleGenerate() {
    if (!nume.trim()) return;
    if (gazdaFile && gazdaFile.size > MAX_UPLOAD_BYTES) {
      setError(
        `Fișierul are ${(gazdaFile.size / 1024 / 1024).toFixed(1)}MB — peste limita de 50MB a storage-ului.`
      );
      setState("error");
      return;
    }
    setState("processing");
    setFormError("");
    setError("");
    setStep(null);
    cancelledRef.current = false;

    let gazdaStoragePath: string | null = null;
    const gazdaFilename: string | null = gazdaFile ? gazdaFile.name : null;

    if (gazdaFile) {
      setProgress("Încarc documentul gazdă...");
      try {
        try {
          const up = await uploadSourceFile(gazdaFile, "scop-core");
          gazdaStoragePath = up.storage_path;
        } catch (initErr) {
          const msg = initErr instanceof Error ? initErr.message : "";
          if (!isColdStartError(msg)) throw initErr;
          setProgress("Server pornit, se retransmite automat...");
          await new Promise((r) => setTimeout(r, 5000));
          if (cancelledRef.current) return;
          const up = await uploadSourceFile(gazdaFile, "scop-core");
          gazdaStoragePath = up.storage_path;
        }
      } catch (err) {
        if (cancelledRef.current) return;
        setError(err instanceof Error ? err.message : "Eroare necunoscută la încărcarea gazdei");
        setState("error");
        return;
      }
    }
    if (cancelledRef.current) return;

    setProgress("Generez documentul complet (11 capitole)...");
    const { config, continut } = construiesteCerere();
    try {
      const { job_id } = await postScopCoreGenereazaDocument({
        gazdaStoragePath,
        gazdaFilename,
        config,
        continut,
      });

      const job = await pollJob(() => getScopCoreJob(job_id), {
        cancelled: () => cancelledRef.current,
        onStep: (s) => {
          setStep(s);
          setProgress("Generez documentul complet (11 capitole)...");
        },
      });
      if (!job) return;

      setResult({
        filename: job.filename!,
        docxB64: job.docx_b64!,
        summary: (job.summary as ScopCoreDocumentSummary) ?? null,
      });
      setState("done");
      onGenerated();
    } catch (err: unknown) {
      if (cancelledRef.current) return;
      // Eroare din apelul sincron de generare (422 de validare, sau 500 neașteptat) — rămâne pe
      // formular, ca utilizatorul să corecteze fără să piardă ce a completat.
      setFormError(err instanceof Error ? err.message : "Eroare necunoscută");
      setState("idle");
      formErrorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function reset() {
    cancelledRef.current = true;
    setResult(null);
    setState("idle");
    setError("");
    setFormError("");
  }

  function renuntaLaAsteptare() {
    cancelledRef.current = true;
    setState("idle");
  }

  if (state === "processing") {
    return <ProcessingSpinner label={progress} onCancel={renuntaLaAsteptare} step={step} />;
  }

  if (state === "error") {
    return (
      <div className="flex flex-col gap-3">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
          {error}
        </div>
        <button
          onClick={() => {
            setState("idle");
            setError("");
          }}
          className="text-sm text-[#18257f] underline"
        >
          Încearcă din nou
        </button>
      </div>
    );
  }

  if (state === "done" && result) {
    const s = result.summary;
    return (
      <div className="flex flex-col gap-4">
        {s && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-[#18257f]">{s.capitole_scrise}</p>
              <p className="text-[11px] text-slate-500">capitole scrise</p>
            </div>
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-[#18257f]">{s.module_core}</p>
              <p className="text-[11px] text-slate-500">module CORE</p>
            </div>
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-[#18257f]">{s.elemente_suplimentare_plasate}</p>
              <p className="text-[11px] text-slate-500">elemente suplimentare</p>
            </div>
            <div className="bg-white border border-[#e2e5f0] rounded-lg p-3 text-center">
              <p className="text-xl font-bold text-[#18257f]">{s.cerinte_plasate}</p>
              <p className="text-[11px] text-slate-500">
                cerințe — A:{s.cerinte_pe_incadrare.A} P:{s.cerinte_pe_incadrare.P} D:
                {s.cerinte_pe_incadrare.D} N:{s.cerinte_pe_incadrare.N}
              </p>
            </div>
          </div>
        )}

        {!!s?.avertisment && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            {s.avertisment}
          </p>
        )}

        <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
          <button
            onClick={() => descarca(result.docxB64, result.filename)}
            className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66]"
          >
            ↓ Descarcă documentul de scop (.docx)
          </button>
          <button onClick={reset} className="text-sm text-[#18257f] underline mt-1">
            + Generează alt document
          </button>
        </div>
      </div>
    );
  }

  const coloaneAcoperire: ColoanaTabel<CerintaUI>[] = [
    { cheie: "zona", eticheta: "Zonă", tip: "text", clasa: "w-32" },
    { cheie: "cerinta", eticheta: "Cerință", tip: "textarea" },
    { cheie: "raspuns", eticheta: "Răspunsul soluției", tip: "textarea" },
    { cheie: "incadrare", eticheta: "Încadrare", tip: "select", optiuni: OPTIUNI_INCADRARE, clasa: "w-40" },
  ];
  const coloaneDelimitare: ColoanaTabel<DelimitareRandUI>[] = [
    { cheie: "zona", eticheta: "Zonă", tip: "text", clasa: "w-40" },
    { cheie: "tratat_in", eticheta: "Tratată în", tip: "text", clasa: "w-40" },
    { cheie: "interfatare", eticheta: "Punctul de interfațare", tip: "textarea" },
  ];
  const coloaneFlux: ColoanaTabel<FluxRandUI>[] = [
    { cheie: "etapa", eticheta: "Etapa", tip: "text", clasa: "w-40" },
    { cheie: "ce_se_intampla", eticheta: "Ce se întâmplă în Charisma", tip: "textarea" },
    { cheie: "rezultat", eticheta: "Rezultat", tip: "textarea" },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* 1. Clientul */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-[#18257f]">Clientul</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">
              Nume <span className="font-normal text-slate-400">(obligatoriu)</span>
            </label>
            <input
              type="text"
              value={nume}
              onChange={(e) => setNume(e.target.value)}
              placeholder="Denumirea scurtă a clientului"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">
              Nume complet <span className="font-normal text-slate-400">(opțional)</span>
            </label>
            <input
              type="text"
              value={numeComplet}
              onChange={(e) => setNumeComplet(e.target.value)}
              placeholder="Denumirea juridică completă"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
            />
          </div>
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1">
            Domeniul de activitate <span className="font-normal text-slate-400">(opțional)</span>
          </label>
          <input
            type="text"
            value={domeniu}
            onChange={(e) => setDomeniu(e.target.value)}
            placeholder="Ex. Producție și distribuție de produse lactate"
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1">
            Entități <span className="font-normal text-slate-400">(opțional — câte una pe linie, pentru un grup)</span>
          </label>
          <textarea
            value={entitatiText}
            onChange={(e) => setEntitatiText(e.target.value)}
            rows={2}
            placeholder={"Societatea A SRL\nSocietatea B SRL"}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1">
            Observații <span className="font-normal text-slate-400">(opțional)</span>
          </label>
          <textarea
            value={observatii}
            onChange={(e) => setObservatii(e.target.value)}
            rows={2}
            className="w-full border border-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-[#18257f]"
          />
        </div>
      </div>

      {/* 2. Documentul gazdă */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-[#18257f]">
          Document gazdă <span className="font-normal text-slate-400">(opțional)</span>
        </h3>
        <p className="text-xs text-slate-500 leading-relaxed">
          Spre deosebire de modul „capitol”, aici documentul gazdă NU e obligatoriu: fără el,
          documentul complet pornește de la zero, cu stilurile implicite. Dacă alegi unul, se
          preiau doar stilurile — nimic din conținutul lui.
        </p>
        <UploadZone accept=".docx" label="documentul gazdă (.docx), opțional" onFile={setGazdaFile} />
        {gazdaFile && (
          <div className="flex items-center justify-between gap-3 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
            <span className="text-xs font-medium text-[#131e66] truncate">{gazdaFile.name}</span>
            <button
              onClick={() => setGazdaFile(null)}
              className="text-xs text-slate-400 hover:text-red-600 shrink-0"
            >
              ✕ Elimină
            </button>
          </div>
        )}
      </div>

      {/* 3. Referirea la documentul de Producție */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[#18257f]">
            Referirea la documentul de Producție{" "}
            <span className="font-normal text-slate-400">(opțional)</span>
          </h3>
          <p className="text-xs text-slate-500 leading-relaxed mt-1">
            Completată, activează capitolul de delimitare față de documentul-frate — mai jos,
            cu rândurile lui.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">
              Titlul documentului de Producție
            </label>
            <input
              type="text"
              value={frateTitlu}
              onChange={(e) => setFrateTitlu(e.target.value)}
              placeholder="Ex. Descrierea Soluției Ofertate — Producție"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">
              Aria acoperită de el
            </label>
            <input
              type="text"
              value={frateArie}
              onChange={(e) => setFrateArie(e.target.value)}
              placeholder="Ex. Fabricația și rețetele de producție"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
            />
          </div>
        </div>
        {frateExista && (
          <div>
            <label className="block text-xs font-semibold text-slate-500 mb-1">
              Delimitarea, rând cu rând
            </label>
            <TabelEditabil
              randuri={delimitareRows}
              coloane={coloaneDelimitare}
              onAdauga={adaugaDelimitare}
              onModifica={modificaDelimitare}
              onSterge={stergeDelimitare}
              etichetaAdauga="+ Adaugă un rând de delimitare"
              golMesaj="Niciun rând încă — fără rânduri, capitolul de delimitare nu apare în document."
            />
          </div>
        )}
      </div>

      {/* 4. Secțiunile adăugate peste standard */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[#18257f]">
            Secțiunile adăugate peste standard{" "}
            <span className="font-normal text-slate-400">(opțional)</span>
          </h3>
          <p className="text-xs text-slate-500 leading-relaxed mt-1">
            Ce primește clientul peste standardul CORE — fie în interiorul unui modul existent,
            fie ca subcapitol propriu în capitolul 4.
          </p>
        </div>

        {titluriDuplicate.length > 0 && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            Titluri identice între secțiuni cu subcapitol propriu: {titluriDuplicate.join(", ")}.
            Backend-ul le va contopi într-una singură — dă-le titluri unice.
          </p>
        )}

        {suplimentare.map((el) => (
          <SectiuneSuplimentaraCard
            key={el.id}
            element={el}
            onModifica={modificaSuplimentar}
            onSterge={stergeSuplimentar}
          />
        ))}
        <button
          onClick={adaugaSuplimentar}
          className="self-start text-xs font-semibold text-[#18257f] underline"
        >
          + Adaugă o secțiune
        </button>

        <div className="border-t border-slate-100 pt-3 mt-1">
          <label className="block text-xs font-semibold text-slate-500 mb-1.5">
            Ordinea subcapitolelor capitolului 4
          </label>
          <OrdineCap4 items={ordine} eticheta={etichetaOrdine} onMuta={mutaOrdine} />
        </div>
      </div>

      {/* 5. Matricea de acoperire */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[#18257f]">
            Matricea de acoperire <span className="font-normal text-slate-400">(opțional)</span>
          </h3>
          <p className="text-xs text-slate-500 leading-relaxed mt-1">
            Fără nicio cerință, capitolul „Analiza de acoperire” nu apare deloc în document.
            Enter în ultimul rând adaugă unul nou.
          </p>
        </div>
        {acoperireRows.length > 0 && (
          <div className="flex gap-2 text-[11px] flex-wrap">
            <span className="bg-slate-100 text-slate-600 rounded px-2 py-0.5">
              {acoperireRows.length} cerințe
            </span>
            <span className="bg-emerald-50 text-emerald-700 rounded px-2 py-0.5">
              A: {numarPeIncadrare.A}
            </span>
            <span className="bg-sky-50 text-sky-700 rounded px-2 py-0.5">
              P: {numarPeIncadrare.P}
            </span>
            <span className="bg-amber-50 text-amber-700 rounded px-2 py-0.5">
              D: {numarPeIncadrare.D}
            </span>
            <span className="bg-red-50 text-red-700 rounded px-2 py-0.5">
              N: {numarPeIncadrare.N}
            </span>
          </div>
        )}
        <TabelEditabil
          randuri={acoperireRows}
          coloane={coloaneAcoperire}
          onAdauga={adaugaCerinta}
          onModifica={modificaCerinta}
          onSterge={stergeCerinta}
          etichetaAdauga="+ Adaugă o cerință"
          golMesaj="Nicio cerință încă."
        />
      </div>

      {/* 6. Fluxul operațional */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[#18257f]">
            Fluxul operațional <span className="font-normal text-slate-400">(opțional)</span>
          </h3>
          <p className="text-xs text-slate-500 leading-relaxed mt-1">
            Devine subcapitolul 4.1. Fără rânduri, nu apare deloc.
          </p>
        </div>
        <TabelEditabil
          randuri={fluxRows}
          coloane={coloaneFlux}
          onAdauga={adaugaFlux}
          onModifica={modificaFlux}
          onSterge={stergeFlux}
          etichetaAdauga="+ Adaugă o etapă"
          golMesaj="Nicio etapă încă."
        />
      </div>

      {/* 7. Comutatoare pe capitole */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-[#18257f]">Capitolele documentului</h3>
        <ComutatoareCapitole
          valori={capitoleEfective}
          blocate={blocateCapitole}
          onSchimba={(cheie, valoare) =>
            setCapitoleManual((c) => ({ ...c, [cheie]: valoare }))
          }
        />
      </div>

      {/* 8. Forma capitolului 6 + diacritice */}
      <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
        <div>
          <label className="block text-xs font-semibold text-slate-500 mb-1.5">
            Forma capitolului „Analiza de acoperire”
          </label>
          <div className="flex rounded-lg border border-slate-200 overflow-hidden w-fit">
            <button
              onClick={() => setFormaAcoperire("apdn")}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                formaAcoperire === "apdn"
                  ? "bg-[#18257f] text-white"
                  : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              A / P / D / N separate
            </button>
            <button
              onClick={() => setFormaAcoperire("trei-grupe")}
              className={`px-4 py-2 text-sm font-medium transition-colors border-l border-slate-200 ${
                formaAcoperire === "trei-grupe"
                  ? "bg-[#18257f] text-white"
                  : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              Trei grupe consolidate
            </button>
          </div>
        </div>
        <label className="flex items-start gap-2.5 cursor-pointer">
          <input
            type="checkbox"
            checked={faraDiacritice}
            onChange={(e) => setFaraDiacritice(e.target.checked)}
            className="mt-0.5 w-4 h-4 accent-[#18257f]"
          />
          <span className="text-sm text-slate-700">
            <span className="font-semibold text-[#18257f]">Fără diacritice</span>
            <span className="block text-xs text-slate-500 mt-0.5">
              Unele documente ale clienților se scriu fără ș ț ă î â — bifează dacă e cazul aici.
            </span>
          </span>
        </label>
      </div>

      {formError && (
        <div
          ref={formErrorRef}
          className="bg-red-50 border border-red-300 rounded-lg p-4 text-sm text-red-800"
        >
          <p className="font-semibold mb-0.5">Generarea nu a putut porni</p>
          <p>{formError}</p>
        </div>
      )}

      <button
        onClick={handleGenerate}
        disabled={!potGenera}
        className="w-full bg-[#18257f] text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-[#131e66] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Generează documentul complet
      </button>
      {!nume.trim() && (
        <p className="text-xs text-amber-700 -mt-2">
          Completează numele clientului pentru a continua — restul câmpurilor sunt opționale.
        </p>
      )}
    </div>
  );
}
