import { redirect } from "next/navigation";
import { changePasswordAction } from "@/app/actions/account";

const ERRORS: Record<string, string> = {
  wrong_password: "Parola actuală nu este corectă.",
  weak_password: "Parola nouă trebuie să aibă cel puțin 8 caractere.",
  mismatch: "Parola nouă și confirmarea nu coincid.",
  same_password: "Parola nouă trebuie să fie diferită de cea actuală.",
  unauthorized: "Sesiune expirată — autentifică-te din nou.",
  server_error: "Eroare de server. Încearcă din nou.",
};

export default async function AccountPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; success?: string }>;
}) {
  const { error, success } = await searchParams;
  const errorMsg = error && Object.hasOwn(ERRORS, error) ? ERRORS[error] : null;

  async function handleChangePassword(formData: FormData) {
    "use server";
    const current = String(formData.get("current") ?? "");
    const next = String(formData.get("new") ?? "");
    const confirm = String(formData.get("confirm") ?? "");

    if (next !== confirm) {
      redirect("/account?error=mismatch");
    }

    let errorCode: string | undefined;
    try {
      await changePasswordAction(current, next);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "server_error";
      errorCode = Object.hasOwn(ERRORS, msg) ? msg : "server_error";
    }
    if (errorCode) {
      redirect(`/account?error=${errorCode}`);
    }
    redirect("/account?success=1");
  }

  return (
    <div className="p-8 max-w-md">
      <h1 className="text-xl font-bold text-[#1e3a5f] mb-2">Contul meu</h1>
      <p className="text-sm text-slate-500 mb-6">
        Schimbă parola contului tău. După salvare, folosește parola nouă la
        următoarea autentificare.
      </p>

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4 text-sm text-green-700">
          Parola a fost schimbată cu succes!
        </div>
      )}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm text-red-700">
          {errorMsg}
        </div>
      )}

      <form action={handleChangePassword} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Parola actuală
          </label>
          <input
            type="password"
            name="current"
            autoComplete="current-password"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Parola nouă
          </label>
          <input
            type="password"
            name="new"
            autoComplete="new-password"
            minLength={8}
            placeholder="minim 8 caractere"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Confirmă parola nouă
          </label>
          <input
            type="password"
            name="confirm"
            autoComplete="new-password"
            minLength={8}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#18257f]"
            required
          />
        </div>
        <button
          type="submit"
          className="w-full bg-[#18257f] text-white py-2 rounded-lg text-sm font-semibold hover:bg-[#131e66]"
        >
          Salvează parola nouă
        </button>
      </form>
    </div>
  );
}
