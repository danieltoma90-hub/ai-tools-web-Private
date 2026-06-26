const ERROR_MESSAGES: Record<string, string> = {
  invalid_credentials: "Email sau parolă incorectă.",
  server_error: "Eroare de server. Încearcă din nou.",
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  const errorMsg =
    error && Object.hasOwn(ERROR_MESSAGES, error)
      ? ERROR_MESSAGES[error]
      : null;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white p-8 rounded-xl shadow-md w-full max-w-sm">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-[#1e3a5f]">AI Tools</h1>
          <p className="text-sm text-gray-500 mt-1">TotalSoft</p>
        </div>
        <form method="POST" action="/api/auth/login" className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              name="email"
              autoComplete="email"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Parolă
            </label>
            <input
              type="password"
              name="password"
              autoComplete="current-password"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          {errorMsg && <p className="text-sm text-red-600">{errorMsg}</p>}
          <button
            type="submit"
            className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-semibold hover:bg-blue-700"
          >
            Intră în cont
          </button>
        </form>
      </div>
    </div>
  );
}
