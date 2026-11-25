"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSession } from "@/lib/session";
import { DemoBanner } from "@/components/ui";

type Tone = "command" | "admin";

const COMMAND_NAV = [
  { href: "/command", label: "Overview" },
  { href: "/command/cameras", label: "Cameras" },
  { href: "/command/monitoring", label: "Monitoring" },
  { href: "/command/videos", label: "Videos & Jobs" },
  { href: "/command/incidents", label: "Events" },
  { href: "/command/hotspots", label: "Hotspots" },
  { href: "/command/investigations", label: "Investigations" },
];

const ADMIN_NAV = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/departments", label: "Departments" },
  { href: "/admin/contractors", label: "Contractors" },
  { href: "/admin/assets", label: "Assets" },
  { href: "/admin/contracts", label: "Contracts" },
  { href: "/admin/investigations", label: "Investigations" },
  { href: "/admin/work-orders", label: "Work orders" },
  { href: "/admin/analytics", label: "Analytics" },
  { href: "/admin/audit-logs", label: "Audit trail" },
  { href: "/admin/users", label: "Users & roles" },
];

export function AppShell({
  tone,
  children,
}: {
  tone: Tone;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { session, loading, signOut } = useSession();
  const nav = tone === "command" ? COMMAND_NAV : ADMIN_NAV;

  const shellClass =
    tone === "command"
      ? "min-h-screen bg-[#070d16] text-slate-200"
      : "min-h-screen bg-[#f6f8fb] text-slate-900";
  const asideClass =
    tone === "command"
      ? "border-r border-[#1e2b3c] bg-[#0b1320]"
      : "border-r border-[#dfe6ee] bg-white";
  const topClass =
    tone === "command" ? "border-b border-[#1e2b3c] bg-[#0b1320]" : "border-b border-[#dfe6ee] bg-white";

  return (
    <div className={shellClass}>
      <div className="flex min-h-screen">
        <aside className={`hidden w-60 shrink-0 flex-col p-3 lg:flex ${asideClass}`}>
          <div className="px-2 py-3">
            <p className="text-sm font-semibold tracking-wide">
              ROADGUARD <span className={tone === "command" ? "text-sky-400" : "text-blue-700"}>AI</span>
            </p>
            <p className={`mt-0.5 text-xs ${tone === "command" ? "text-slate-500" : "text-slate-500"}`}>
              {tone === "command" ? "Command Center" : "Administrative Portal"}
            </p>
          </div>
          <nav aria-label={`${tone} navigation`} className="mt-2 space-y-0.5">
            {nav.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + "/");
              const activeClass =
                tone === "command"
                  ? "bg-sky-500/15 text-sky-200"
                  : "bg-blue-50 text-blue-800";
              const idleClass =
                tone === "command"
                  ? "text-slate-400 hover:bg-[#131e2c] hover:text-slate-200"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900";
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`block rounded-lg px-3 py-2 text-sm transition ${active ? activeClass : idleClass}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto space-y-2 px-2 pb-2 pt-6 border-t border-opacity-50">
            <Link
              href={tone === "command" ? "/admin" : "/command"}
              className={`block rounded-lg px-3 py-2 text-xs font-medium ${
                tone === "command"
                  ? "bg-[#131e2c] text-sky-300 hover:bg-[#1a2837] border border-[#243449]"
                  : "bg-slate-100 text-blue-800 hover:bg-slate-200 border border-slate-200"
              }`}
            >
              {tone === "command" ? "Open Administrative Portal →" : "← Back to Command Center"}
            </Link>
            {session && (
              <button
                type="button"
                onClick={() => void signOut()}
                className={`w-full rounded-lg px-3 py-2 text-xs font-medium text-left ${
                  tone === "command"
                    ? "border border-[#243449] text-slate-300 hover:bg-[#131e2c]"
                    : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                Sign out
              </button>
            )}
            <p className={`text-[11px] ${tone === "command" ? "text-slate-500" : "text-slate-500"}`}>
              Prototype · human review required for every official decision.
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className={`sticky top-0 z-20 ${topClass}`}>
            <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="flex items-center gap-3">
                <span className={`text-sm font-semibold lg:hidden`}>ROADGUARD AI</span>
                {session ? (
                  <span
                    className={`hidden rounded-full px-2 py-0.5 text-xs ring-1 ring-inset sm:inline ${
                      tone === "command"
                        ? "bg-[#131e2c] text-slate-300 ring-[#243449]"
                        : "bg-slate-100 text-slate-700 ring-slate-200"
                    }`}
                  >
                    {session.user.organization.name}
                  </span>
                ) : null}
              </div>
              <div className="flex items-center gap-3 text-xs">
                {loading ? (
                  <span className={tone === "command" ? "text-slate-500" : "text-slate-500"}>
                    Loading session…
                  </span>
                ) : session ? (
                  <>
                    <span className="hidden text-right sm:block">
                      <span className="block font-medium">{session.user.full_name}</span>
                      <span className={tone === "command" ? "text-slate-500" : "text-slate-500"}>
                        {session.user.role.replace(/_/g, " ")}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => void signOut()}
                      className={`rounded-lg px-2.5 py-1.5 font-medium ${
                        tone === "command"
                          ? "border border-[#243449] text-slate-300 hover:bg-[#131e2c]"
                          : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      Sign out
                    </button>
                  </>
                ) : null}
              </div>
            </div>
            <nav aria-label="mobile navigation" className="flex flex-col lg:hidden gap-2 p-3 border-t border-opacity-50">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`whitespace-nowrap rounded-full px-3 py-2 text-sm ${
                    pathname === item.href || pathname.startsWith(item.href + "/")
                      ? tone === "command"
                        ? "bg-sky-500/20 text-sky-200"
                        : "bg-blue-100 text-blue-800"
                      : tone === "command"
                        ? "text-slate-400"
                        : "text-slate-600"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
              {session && (
                <button
                  type="button"
                  onClick={() => void signOut()}
                  className={`w-full rounded-lg px-3 py-2 text-sm font-medium text-left ${
                    tone === "command"
                      ? "border border-[#243449] text-slate-300 hover:bg-[#131e2c]"
                      : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  Sign out
                </button>
              )}
            </nav>
          </header>
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-5">
            <div className="mb-4">
              <DemoBanner tone={tone} />
            </div>
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
