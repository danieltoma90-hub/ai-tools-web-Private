const PROXY = "/api/proxy";

async function postFile(path: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${PROXY}/${path}`, { method: "POST", body: form });
  if (!res.ok) {
    let detail = "Eroare server";
    try {
      const data = await res.json();
      detail = data.detail ?? detail;
    } catch {
      detail = (await res.text().catch(() => "")) || detail;
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
    html_compact: string;
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
