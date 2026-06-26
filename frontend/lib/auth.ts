import { loginAction } from "@/app/actions/auth";

export async function login(email: string, password: string) {
  await loginAction(email, password);
}

export async function logout() {
  await fetch("/api/auth/clear-session", { method: "POST" });
  window.location.href = "/login";
}
