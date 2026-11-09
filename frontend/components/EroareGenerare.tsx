/** Eroarea unei generări, cu drumul înapoi la formular. */
export default function EroareGenerare({ eroare, onReset }: { eroare: string; onReset: () => void }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
        {eroare}
        {eroare.includes("expirat") && (
          <p className="mt-2 text-xs">Serverul a fost repornit între timp — reîncarcă fișierul și reia.</p>
        )}
      </div>
      <button onClick={onReset} className="text-sm text-[#18257f] underline w-fit">
        Încearcă din nou
      </button>
    </div>
  );
}
