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
  filename?: string;
  docx_b64?: string;
  preview_html?: string;
  storage_path?: string;
  error?: string;
}> {
  return apiFetch(`${PROXY}/minuta/job/${jobId}`) as Promise<{
    status: "processing" | "done" | "error";
    filename?: string;
    docx_b64?: string;
    preview_html?: string;
    storage_path?: string;
    error?: string;
  }>;
}

export async function postMinutaFree(file: File): Promise<{
  filename: string;
  docx_b64: string;
  preview_html: string;
  storage_path: string;
}> {
  return postFile("minuta-free", file) as Promise<{
    filename: string;
    docx_b64: string;
    preview_html: string;
    storage_path: string;
  }>;
}

export async function postMockup(file: File) {
  return postFile("mockup", file) as Promise<{
    filename: string;
    docx_b64: string;
    html: string;
  }>;
}

export async function postScenarii(file: File) {
  return postFile("scenarii", file) as Promise<{
    filename: string;
    xlsx_b64: string;
  }>;
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
