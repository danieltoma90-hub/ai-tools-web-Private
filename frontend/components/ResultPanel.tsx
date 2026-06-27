"use client";

type Props = {
  filename: string;
  docxB64: string;
  previewHtml: string;
  onReset: () => void;
  downloadLabel?: string;
  resetLabel?: string;
};

function b64toBlob(b64: string, type: string) {
  const bytes = atob(b64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  return new Blob([arr], { type });
}

export default function ResultPanel({
  filename,
  docxB64,
  previewHtml,
  onReset,
  downloadLabel = "↓ Descarcă .docx",
  resetLabel = "+ Generează alta",
}: Props) {
  const ext = filename.split(".").pop()?.toLowerCase();
  const mimeType =
    ext === "xlsx"
      ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      : "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

  function downloadFile() {
    const blob = b64toBlob(docxB64, mimeType);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function openPreview() {
    const blob = new Blob([previewHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
        <span className="text-2xl">✅</span>
        <div>
          <p className="font-semibold text-green-800">Generat cu succes!</p>
          <p className="text-xs text-green-600 mt-0.5">{filename}</p>
        </div>
      </div>

      {docxB64 && (
        <button
          onClick={downloadFile}
          className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-700"
        >
          {downloadLabel}
        </button>
      )}

      {previewHtml && (
        <button
          onClick={openPreview}
          className="w-full bg-white border border-blue-600 text-blue-600 py-2.5 rounded-lg text-sm font-semibold hover:bg-blue-50"
        >
          👁 Preview în tab nou
        </button>
      )}

      <button
        onClick={onReset}
        className="w-full bg-slate-100 text-slate-600 py-2.5 rounded-lg text-sm hover:bg-slate-200"
      >
        {resetLabel}
      </button>
    </div>
  );
}
