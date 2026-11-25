"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Session } from "@/lib/types";

const DEMO_PASSWORD = "RoadguardDemo#2026";

const DEMO_ACCOUNTS = [
  ["ops@demo.roadguard.ai", "Operations administrator"],
  ["reviewer@demo.roadguard.ai", "Event reviewer / verifier"],
  ["engineer@demo.roadguard.ai", "Department engineer"],
  ["auditor@demo.roadguard.ai", "Auditor (read only)"],
  ["admin@demo.roadguard.ai", "Organization administrator"],
];

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post<Session>("/api/v1/auth/login", { email, password });
      const next = params.get("next");
      router.replace(next && next.startsWith("/") ? next : "/command");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Sign-in failed. Check the API is running and try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#070d16] px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold tracking-wide text-slate-100">
            ROADGUARD <span className="text-sky-400">AI</span>
          </p>
          <p className="mt-1 text-sm text-slate-400">
            Road-safety review and corrective-action tracking
          </p>
        </div>
        <form
          onSubmit={submit}
          className="space-y-4 rounded-xl border border-[#1e2b3c] bg-[#0f1723] p-6 shadow-xl"
        >
          <div>
            <label htmlFor="email" className="mb-1 block text-sm font-medium text-slate-200">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border border-[#243449] bg-[#0b1320] px-3 py-2 text-sm text-slate-100"
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-slate-200">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-[#243449] bg-[#0b1320] px-3 py-2 text-sm text-slate-100"
            />
          </div>
          {error ? (
            <p role="alert" className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-200">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-sky-500 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-xs text-slate-500">
            Roles are assigned by an administrator on the server. You cannot choose a role at
            sign-in.
          </p>
        </form>

        <div className="mt-5 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
          <p className="text-xs font-semibold text-amber-200">DEMO CREDENTIALS</p>
          <p className="mt-1 text-xs text-amber-100/90">
            Password: <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono font-medium text-amber-300">RoadguardDemo#2026</code>
          </p>
          <p className="mt-1 text-xs text-amber-100/70">
            Click any account below to autofill both email & password:
          </p>
          <ul className="mt-2.5 space-y-1.5 text-xs text-amber-100/90">
            {DEMO_ACCOUNTS.map(([account, role]) => (
              <li key={account} className="flex items-center justify-between">
                <button
                  type="button"
                  className="rounded px-1.5 py-0.5 text-left font-mono underline decoration-dotted hover:bg-amber-400/10 hover:text-amber-200"
                  onClick={() => {
                    setEmail(account);
                    setPassword(DEMO_PASSWORD);
                    setError(null);
                  }}
                >
                  {account}
                </button>
                <span className="text-slate-400 text-[11px]">{role}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#070d16]" />}>
      <LoginForm />
    </Suspense>
  );
}
