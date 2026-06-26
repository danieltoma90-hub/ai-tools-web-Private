import { redirect } from "next/navigation";
import { inviteUserAction } from "@/app/actions/invite";

const ERRORS: Record<string, string> = {
  exists: "Un utilizator cu acest email există deja.",
  server_error: "Eroare de server. Încearcă din nou.",
};

export default async function InvitePage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; success?: string }>;
}) {
  const { error, success } = await searchParams;
  const errorMsg =
    error && Object.hasOwn(ERRORS, error) ? ERRORS[error] : null;

  async function handleInvite(formData: FormData) {
    "use server";
    const email = formData.get("email") as string;
    let errorCode: string | undefined;
    try {
      await inviteUserAction(email);
    } catch (e) {
      const msg = e instanceof Error ? e.message.toLowerCase() : "";
      errorCode =
        msg.includes("already") || msg.includes("exists")
          ? "exists"
          : "server_error";
    }
    if (errorCode) {
      redirect(`/invite?error=${errorCode}`);
    }
    redirect("/invite?success=1");
  }

  return (
    <div className="p-8 max-w-md">
      <h1 className="text-xl font-bold text-[#1e3a5f] mb-2">Invită utilizator</h1>
      <p className="text-sm text-slate-500 mb-6">
        Utilizatorul va primi un email cu link de activare cont.
      </p>

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4 text-sm text-green-700">
          Invitație trimisă cu succes!
        </div>
      )}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm text-red-700">
          {errorMsg}
        </div>
      )}

      <form action={handleInvite} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Email coleg
          </label>
          <input
            type="email"
            name="email"
            placeholder="coleg@totalsoft.ro"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>
        <button
          type="submit"
          className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-semibold hover:bg-blue-700"
        >
          Trimite invitație
        </button>
      </form>
    </div>
  );
}
