const ERORI: Record<string, string> = {
  email: "Adresa de email nu pare corectă.",
  prea_des: "Ai cerut deja un link. Așteaptă un minut și încearcă din nou.",
  link_expirat: "Linkul a expirat sau a fost deja folosit. Cere unul nou mai jos.",
  server: "Eroare de server. Încearcă din nou.",
};

/** „Am uitat parola”: utilizatorul primește pe email un link cu care își alege singur parola nouă. */
export default async function ParolaUitataPage({
  searchParams,
}: {
  searchParams: Promise<{ trimis?: string; eroare?: string }>;
}) {
  const { trimis, eroare } = await searchParams;
  const mesajEroare = eroare && Object.hasOwn(ERORI, eroare) ? ERORI[eroare] : null;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-[#1e3a5f] italic">AI Tools</h1>
          <span className="inline-block h-[3px] w-14 bg-[#ffd500] mt-1" />
        </div>

        {trimis ? (
          <div className="space-y-4">
            <h2 className="text-base font-semibold text-[#18257f]">Verifică emailul</h2>
            <p className="text-sm text-gray-700">
              Dacă adresa are cont în AI Tools, vei primi în câteva minute un email cu linkul de resetare a
              parolei. Linkul este valabil o oră și se poate folosi o singură dată.
            </p>
            <p className="text-xs text-gray-500">Nu îl găsești? Verifică și folderul Spam / Junk.</p>
          </div>
        ) : (
          <form method="POST" action="/api/auth/recover" className="space-y-4">
            <div>
              <h2 className="text-base font-semibold text-[#18257f]">Ai uitat parola?</h2>
              <p className="text-sm text-gray-600 mt-1">
                Scrie adresa de email a contului. Îți trimitem un link cu care îți alegi singur parola nouă.
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                name="email"
                autoComplete="email"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
                required
              />
            </div>
            {mesajEroare && <p className="text-sm text-red-600">{mesajEroare}</p>}
            <button
              type="submit"
              className="w-full bg-[#18257f] text-white py-2 rounded-lg text-sm font-semibold hover:bg-[#131e66]"
            >
              Trimite linkul de resetare
            </button>
          </form>
        )}

        <p className="text-center mt-5">
          <a href="/login" className="text-sm text-[#18257f] hover:underline">
            ← Înapoi la conectare
          </a>
        </p>
      </div>
    </div>
  );
}
