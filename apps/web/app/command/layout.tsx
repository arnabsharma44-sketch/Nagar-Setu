import { AppShell } from "@/components/AppShell";

export default function CommandLayout({ children }: { children: React.ReactNode }) {
  return <AppShell tone="command">{children}</AppShell>;
}
