import { getToken } from "./auth";

const API = process.env.NEXT_PUBLIC_API_URL!;

async function authHeaders() {
  const token = await getToken();
  return { Authorization: `Bearer ${token}` };
}

export async function postMinuta(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/api/minuta`, {
    method: "POST",
    headers: await authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Eroare server");
  return res.json() as Promise<{
    filename: string;
    docx_b64: string;
    preview_html: string;
    storage_path: string;
  }>;
}

export async function postMockup(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/api/mockup`, {
    method: "POST",
    headers: await authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Eroare server");
  return res.json() as Promise<{
    filename: string;
    docx_b64: string;
    html: string;
    html_compact: string;
  }>;
}

export async function postScenarii(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}/api/scenarii`, {
    method: "POST",
    headers: await authHeaders(),
    body: form,
  });
  if (!res.ok) throw new Error((await res.json()).detail ?? "Eroare server");
  return res.json() as Promise<{ filename: string; xlsx_b64: string }>;
}

export async function getDocuments(tool?: string) {
  const url = tool ? `${API}/api/documents?tool=${tool}` : `${API}/api/documents`;
  const res = await fetch(url, { headers: await authHeaders() });
  if (!res.ok) throw new Error("Eroare la încărcarea documentelor");
  return res.json() as Promise<
    { name: string; created_at: string; size: number; download_url: string }[]
  >;
}
