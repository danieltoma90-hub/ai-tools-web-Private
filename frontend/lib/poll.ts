export type JobStatus = {
  status: "processing" | "done" | "error";
  step?: string;
  error?: string;
};

type Options = {
  /** Oprește bucla când utilizatorul a părăsit ecranul sau a anulat. */
  cancelled: () => boolean;
  onStep?: (step: string) => void;
  intervalMs?: number;
  /** Câte interogări consecutive eșuate tolerăm înainte să dăm eroare. */
  maxFailures?: number;
};

/**
 * Urmărește un job până se termină. Întoarce `null` dacă s-a anulat.
 *
 * Jobul rulează pe server, independent de pagină: o interogare de progres
 * eșuată înseamnă aproape întotdeauna o pâlpâire de rețea, nu o generare
 * pierdută. De aceea nu abandonăm din prima — altfel utilizatorul vede eroare
 * pentru un document care se generează în continuare și ajunge în Repository.
 */
export async function pollJob<T extends JobStatus>(
  fetchJob: () => Promise<T>,
  { cancelled, onStep, intervalMs = 2000, maxFailures = 3 }: Options
): Promise<T | null> {
  let failures = 0;

  while (true) {
    await new Promise((r) => setTimeout(r, intervalMs));
    if (cancelled()) return null;

    let job: T;
    try {
      job = await fetchJob();
      failures = 0;
    } catch (err) {
      failures += 1;
      if (failures >= maxFailures) throw err;
      continue;
    }
    if (cancelled()) return null;

    if (job.step && onStep) onStep(job.step);
    if (job.status === "done") return job;
    if (job.status === "error") {
      throw new Error(job.error || "Generarea a eșuat");
    }
  }
}

/** Eroare de pornire tipică pentru Render free tier: serverul dormea. */
export function isColdStartError(msg: string): boolean {
  return (
    msg.includes("timp util") ||
    msg.includes("unreachable") ||
    msg.includes("502") ||
    msg.includes("504")
  );
}
