const PROXY = "/api/proxy";

async function apiFetch(url: string, init?: RequestInit) {
  const res = await fetch(url, init);
  if (!res.ok) {
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

export async function postMinuta(file: File): Promise<{ job_id: string }> {
  return postFile("minuta", file) as Promise<{ job_id: string }>;
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

export async function postMinutaFree(file: File): Promise<{
  job_id: string;
  est_minutes?: number;
  chunks?: number;
}> {
  return postFile("minuta-free", file) as Promise<{
    job_id: string;
    est_minutes?: number;
    chunks?: number;
  }>;
}

export type EstimateResponse = {
  estimate_id: string;
  est_tokens: number;
  est_minutes: number;
  fits_budget: boolean;
  calls?: number;
  modules?: number;
};

export type Scenariu = {
  id: string;
  capitol: string;
  subcapitol: string;
  titlu_scenariu: string;
  obiectiv: string;
  preconditii: string;
  pasi: string;
  rezultat_asteptat: string;
  tip_test: string;
  prioritate: string;
  dependente: string;
  observatii: string;
  ai: boolean;
};

export type ScenariiJob = {
  status: "processing" | "done" | "error";
  step?: string; // "chunk:2/5:Nume" | "building"
  filename?: string;
  xlsx_b64?: string;
  scenarios?: Scenariu[];
  ai_used?: boolean;
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
  tool: "scenarii" | "mockup"
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
  useAi: boolean
): Promise<{ job_id: string }> {
  return postGenerate("scenarii/generate", estimateId, useAi) as Promise<{ job_id: string }>;
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

export async function getDocuments(tool?: string) {
  const url = tool ? `${PROXY}/documents?tool=${tool}` : `${PROXY}/documents`;
  return apiFetch(url) as Promise<
    {
      name: string;
      tool: string;
      owner: string;
      storage_path: string;
      created_at: string;
      size: number;
      download_url: string;
    }[]
  >;
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
