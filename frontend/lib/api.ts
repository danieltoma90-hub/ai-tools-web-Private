const PROXY = "/api/proxy";

async function apiFetch(url: string, init?: RequestInit) {
  const res = await fetch(url, init);
  if (!res.ok) {
    // Sesiunea a expirat și nici reînnoirea din proxy n-a reușit: singura
    // ieșire e autentificarea din nou, nu un mesaj de eroare pe ecran.
    if (res.status === 401 && typeof window !== "undefined") {
      window.location.href = "/login?error=session_expired";
      throw new Error("Sesiune expirată — te reautentifici.");
    }
    // Vercel oprește cererile peste 4,5MB cu o pagină proprie, al cărei text
    // („FUNCTION_PAYLOAD_TOO_LARGE") nu spune nimic utilizatorului.
    if (res.status === 413) {
      throw new Error(
        "Fișierul este prea mare pentru a fi trimis astfel. Reîncarcă pagina " +
          "(Ctrl+Shift+R) și reia — versiunea nouă urcă fișierul direct în storage."
      );
    }
    let detail = "Eroare server";
    try {
      const text = await res.text();
      try {
        const data = JSON.parse(text);
        detail =
          ((typeof data.detail === "string" ? data.detail : null) ??
            data.error?.message ??
            data.message ??
            text) || detail;
      } catch {
        detail = text || detail;
      }
    } catch {
      // body necitibil — rămâne fallback-ul
    }
    throw new Error(detail);
  }
  return res.json();
}

async function postFile(path: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  return apiFetch(`${PROXY}/${path}`, { method: "POST", body: form });
}

export async function postMinuta(
  storagePath: string,
  filename: string,
  contextPath?: string
): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("storage_path", storagePath);
  form.append("filename", filename);
  if (contextPath) form.append("context_path", contextPath);
  return apiFetch(`${PROXY}/minuta`, { method: "POST", body: form }) as Promise<{
    job_id: string;
  }>;
}

export type SavedContext = {
  name: string;
  owner: string;
  storage_path: string;
  created_at: string;
};

export async function getContexts(): Promise<SavedContext[]> {
  return apiFetch(`${PROXY}/minuta/contexts`) as Promise<SavedContext[]>;
}

export async function uploadContext(file: File): Promise<{
  storage_path: string;
  name: string;
  summary: {
    participanti: number;
    glosar: number;
    decizii: number;
    actiuni_deschise: number;
  };
}> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch(`${PROXY}/minuta/contexts`, {
    method: "POST",
    body: form,
  }) as Promise<{
    storage_path: string;
    name: string;
    summary: {
      participanti: number;
      glosar: number;
      decizii: number;
      actiuni_deschise: number;
    };
  }>;
}

/** Template-ul de context: descărcare prin proxy (păstrează autentificarea). */
export async function downloadContextTemplate(): Promise<void> {
  const res = await fetch(`${PROXY}/minuta/context-template`);
  if (!res.ok) throw new Error("Nu s-a putut descărca template-ul.");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "Context_Proiect_Template.docx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function pollMinutaJob(jobId: string): Promise<{
  status: "processing" | "done" | "error";
  step?: string; // "metadata" | "chunk:3/8" | "synthesis" | "building"
  filename?: string;
  docx_b64?: string;
  preview_html?: string;
  storage_path?: string;
  error?: string;
}> {
  return apiFetch(`${PROXY}/minuta/job/${jobId}`) as Promise<{
    status: "processing" | "done" | "error";
    step?: string;
    filename?: string;
    docx_b64?: string;
    preview_html?: string;
    storage_path?: string;
    error?: string;
  }>;
}

export async function postMinutaFree(
  storagePath: string,
  filename: string
): Promise<{
  job_id: string;
  est_minutes?: number;
  chunks?: number;
}> {
  const form = new FormData();
  form.append("storage_path", storagePath);
  form.append("filename", filename);
  return apiFetch(`${PROXY}/minuta-free`, { method: "POST", body: form }) as Promise<{
    job_id: string;
    est_minutes?: number;
    chunks?: number;
  }>;
}

export type EstimateResponse = {
  estimate_id: string;
  est_tokens: number;
  est_minutes: number;
  est_minutes_free?: number;
  requirements?: number;
  fits_budget: boolean;
  calls?: number;
  modules?: number;
};

export type ScenariiSummary = {
  core_count: number;
  specific_count: number;
  excluded_count: number;
  requirements: number;
};

export type ScenariiJob = {
  status: "processing" | "done" | "error";
  step?: string; // "parsing" | "gen:2/5" | "deps" | "building"
  filename?: string;
  xlsx_b64?: string;
  summary?: ScenariiSummary;
  engine?: "claude" | "groq";
  storage_path?: string;
  error?: string;
};

export type MockupJob = {
  status: "processing" | "done" | "error";
  step?: string; // "parsing" | "ai" | "building"
  filename?: string;
  docx_b64?: string;
  html?: string;
  ai_used?: boolean;
  storage_path?: string;
  error?: string;
};

function postGenerate(path: string, estimateId: string, useAi: boolean) {
  return apiFetch(`${PROXY}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estimate_id: estimateId, use_ai: useAi }),
  });
}

export async function uploadSourceFile(
  file: File,
  tool: "scenarii" | "mockup" | "training" | "minuta"
): Promise<{ storage_path: string }> {
  const sign = (await apiFetch(`${PROXY}/uploads/sign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, tool }),
  })) as { storage_path: string; signed_url: string; token: string };

  const res = await fetch(sign.signed_url, {
    method: "PUT",
    headers: { "Content-Type": file.type || "application/octet-stream" },
    body: file,
  });
  if (!res.ok) {
    throw new Error(
      `Încărcarea fișierului în storage a eșuat (cod ${res.status}). Reîncearcă.`
    );
  }
  return { storage_path: sign.storage_path };
}

function postEstimate(path: string, storagePath: string, filename: string) {
  return apiFetch(`${PROXY}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ storage_path: storagePath, filename }),
  });
}

export async function postScenariiEstimate(
  storagePath: string,
  filename: string
): Promise<EstimateResponse> {
  return postEstimate("scenarii/estimate", storagePath, filename) as Promise<EstimateResponse>;
}

export async function postScenariiGenerate(
  estimateId: string,
  engine: "claude" | "groq"
): Promise<{ job_id: string }> {
  return apiFetch(`${PROXY}/scenarii/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estimate_id: estimateId, engine }),
  }) as Promise<{ job_id: string }>;
}

export async function getScenariiJob(jobId: string): Promise<ScenariiJob> {
  return apiFetch(`${PROXY}/scenarii/job/${jobId}`) as Promise<ScenariiJob>;
}

export async function postMockupEstimate(
  storagePath: string,
  filename: string
): Promise<EstimateResponse> {
  return postEstimate("mockup/estimate", storagePath, filename) as Promise<EstimateResponse>;
}

export async function postMockupGenerate(
  estimateId: string,
  useAi: boolean
): Promise<{ job_id: string }> {
  return postGenerate("mockup/generate", estimateId, useAi) as Promise<{ job_id: string }>;
}

export async function getMockupJob(jobId: string): Promise<MockupJob> {
  return apiFetch(`${PROXY}/mockup/job/${jobId}`) as Promise<MockupJob>;
}

export type Doc = {
  name: string;
  tool: string;
  owner: string;
  storage_path: string;
  created_at: string;
  size: number;
  download_url: string;
};

export async function getDocuments(tool?: string): Promise<Doc[]> {
  const url = tool ? `${PROXY}/documents?tool=${tool}` : `${PROXY}/documents`;
  return apiFetch(url) as Promise<Doc[]>;
}

export async function deleteDocument(storagePath: string) {
  return apiFetch(
    `${PROXY}/documents?storage_path=${encodeURIComponent(storagePath)}`,
    { method: "DELETE" }
  );
}

export async function getStorageUsage(): Promise<{
  used_bytes: number;
  quota_bytes: number;
  percent: number;
}> {
  return apiFetch(`${PROXY}/storage/usage`) as Promise<{
    used_bytes: number;
    quota_bytes: number;
    percent: number;
  }>;
}

export type DashboardSummary = {
  total_documents: number;
  week_count: number;
  usage: { used_bytes: number; quota_bytes: number; percent: number };
  documents: {
    name: string;
    tool: string;
    owner: string;
    created_at: string;
    download_url: string;
  }[];
};

export async function getRecentDocuments(
  tool: string,
  limit = 5
): Promise<Doc[]> {
  const q = new URLSearchParams({ tool, limit: String(limit) });
  return apiFetch(`${PROXY}/documents?${q}`) as Promise<Doc[]>;
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return apiFetch(`${PROXY}/dashboard/summary`) as Promise<DashboardSummary>;
}

export type ProviderStatus = {
  provider: string;
  configured: boolean;
  key_hint?: string;
  state:
    | "ok"
    | "cheie_invalida"
    | "fara_credit"
    | "limita_atinsa"
    | "model_indisponibil"
    | "lipsa"
    | "eroare";
  message: string;
};

export async function getProviderDiagnostics(): Promise<{
  providers: ProviderStatus[];
}> {
  return apiFetch(`${PROXY}/diagnostics/providers`) as Promise<{
    providers: ProviderStatus[];
  }>;
}

export type TrainingSummary = {
  tip: string;
  zile: number;
  total_ore: number;
  module: number;
  particularitati: number;
  excluse: string[];
  supraincarcat: boolean;
  /** Efortul cerut de conținut înainte de distribuirea pe zilele alese. */
  ore_referinta?: number;
  /** Setat când specificația n-a putut fi citită, dar agenda standard s-a generat. */
  avertisment?: string;
};

export type TrainingJob = {
  status: "processing" | "done" | "error";
  step?: string; // "catalog" | "specificatie" | "planificare" | "documente"
  filename?: string;
  docx_b64?: string;
  xlsx_filename?: string;
  xlsx_b64?: string;
  summary?: TrainingSummary;
  storage_path?: string;
  error?: string;
};

export async function postTrainingGenerate(params: {
  tip: "core" | "productie";
  zile: number;
  client: string;
  storagePath?: string;
}): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("tip", params.tip);
  form.append("zile", String(params.zile));
  form.append("client", params.client);
  if (params.storagePath) form.append("storage_path", params.storagePath);
  return apiFetch(`${PROXY}/training/generate`, {
    method: "POST",
    body: form,
  }) as Promise<{ job_id: string }>;
}

export async function getTrainingJob(jobId: string): Promise<TrainingJob> {
  return apiFetch(`${PROXY}/training/job/${jobId}`) as Promise<TrainingJob>;
}
