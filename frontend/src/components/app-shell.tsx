import Link from "next/link";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/onboarding", label: "Onboarding" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/forecast", label: "Forecast" },
  { href: "/goals", label: "Goals" },
  { href: "/strategy", label: "Strategy" },
  { href: "/settings", label: "Settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-ws-background text-ws-primary">
      <header className="sticky top-0 z-20 border-b border-ws-border bg-ws-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <Link href="/" className="text-lg font-medium">
            WealthSense AI
          </Link>
          <nav className="hidden gap-4 text-sm md:flex" aria-label="Primary">
            {navItems.map((item) => (
              <Link key={item.href} href={item.href} className="rounded-md px-2 text-[#3d4558] hover:text-ws-primary">
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

