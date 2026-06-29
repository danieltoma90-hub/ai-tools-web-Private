const PROXY = "/api/proxy";

async function postFile(path: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${PROXY}/${path}`, { method: "POST", body: form });
  if (!res.ok) {
    let detail = "Eroare server";
    try {
      // Citim text() o singură dată — json() consumă body-ul și face text() să eșueze
      const text = await res.text();
      try {
        const data = JSON.parse(text);
        // FastAPI: { detail: "..." } | Vercel timeout: { error: { message: "..." } }
        detail =
          (typeof data.detail === "string" ? data.detail : null) ??
          data.error?.message ??
          data.message ??
          text ||
          detail;
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

export async function postMinuta(file: File) {
  return postFile("minuta", file) as Promise<{
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
  const res = await fetch(url);
  if (!res.ok) throw new Error("Eroare la încărcarea documentelor");
  return res.json() as Promise<
    { name: string; created_at: string; size: number; download_url: string }[]
  >;
}
