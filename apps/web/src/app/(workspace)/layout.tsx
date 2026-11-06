import { AppShell } from "@/components/layout/app-shell";
import { Suspense } from "react";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // With Cache Components, AppShell's usePathname needs a runtime boundary
  // on dynamic proposal URLs. The page and shell stream together.
  return (
    <Suspense fallback={<div role="status" className="min-h-screen bg-background p-8 text-sm text-muted">Loading workspace…</div>}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
