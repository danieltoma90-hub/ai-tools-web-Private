"use client";
import { useEffect, useState } from "react";
import {
  downloadContextTemplate,
  getContexts,
  uploadContext,
  type SavedContext,
} from "@/lib/api";

type Props = {
  /** Contextul ales (storage_path) sau "" pentru „fără context". */
  value: string;
  onChange: (storagePath: string, label: string) => void;
};

/** Pasul 1: contextul de proiect — opțional, reutilizabil între ședințe. */
export default function ContextStep({ value, onChange }: Props) {
  const [saved, setSaved] = useState<SavedContext[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [justUploaded, setJustUploaded] = useState<string>("");

  useEffect(() => {
    getContexts()
      .then(setSaved)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleTemplate() {
    setError("");
    try {
      await downloadContextTemplate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Descărcarea a eșuat");
    }
  }

  async function handleFile(file: File) {
    setBusy(true);
    setError("");
    try {
      const res = await uploadContext(file);
      const s = res.summary;
      setJustUploaded(
        `${res.name} — ${s.participanti} participanți, ${s.glosar} termeni, ` +
          `${s.decizii} decizii, ${s.actiuni_deschise} acțiuni deschise`
      );
      setSaved(await getContexts().catch(() => saved));
      onChange(res.storage_path, res.name);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Încărcarea a eșuat");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-[#e2e5f0] rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-[#18257f]">
            Pasul 1 · Context proiect{" "}
            <span className="font-normal text-slate-400">(opțional)</span>
          </h3>
          <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">
            Participanții cu rolurile lor, glosarul de termeni și acțiunile
            rămase deschise. Minuta devine mai precisă și urmărește ce s-a
            închis din ședințele anterioare.
          </p>
        </div>
        <button
          onClick={handleTemplate}
          className="shrink-0 border border-[#d6d9e2] text-[#18257f] hover:bg-[#f1f3f8] rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
        >
          ↓ Descarcă template
        </button>
      </div>

      {saved.length > 0 && (
        <label className="text-xs text-slate-600">
          Context salvat:
          <select
            value={value}
            onChange={(e) => {
              const path = e.target.value;
              const found = saved.find((s) => s.storage_path === path);
              onChange(path, found?.name ?? "");
              setJustUploaded("");
            }}
            className="ml-2 border border-slate-300 rounded-lg px-2 py-1 text-xs"
          >
            <option value="">— fără context —</option>
            {saved.map((s) => (
              <option key={s.storage_path} value={s.storage_path}>
                {s.name} ({s.owner})
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="flex items-center gap-3">
        <label
          className={`text-xs font-semibold px-3 py-1.5 rounded-lg border cursor-pointer transition-colors ${
            busy
              ? "opacity-50 cursor-wait border-slate-200 text-slate-400"
              : "border-[#18257f] text-[#18257f] hover:bg-[#eef0f8]"
          }`}
        >
          {busy ? "Se încarcă..." : saved.length > 0 ? "＋ Încarcă alt context" : "＋ Încarcă context completat"}
          <input
            type="file"
            accept=".docx"
            className="hidden"
            disabled={busy}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
              e.target.value = "";
            }}
          />
        </label>
        {loading && <span className="text-xs text-slate-400">se verifică...</span>}
      </div>

      {justUploaded && (
        <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
          ✓ Context încărcat: {justUploaded}
        </p>
      )}
      {error && (
        <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </p>
      )}
    </div>
  );
}
