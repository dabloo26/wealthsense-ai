import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth } from "@/lib/api";

export default async function Home() {
  const health = await getHealth().catch(() => null);

  return (
    <AppShell>
      <section className="mx-auto flex max-w-4xl flex-col items-center gap-6 py-10 text-center">
        <h1>See where your money is headed. Plain and simple.</h1>

        <p className="max-w-2xl text-[#3d4558]">
          We help you understand if your plan is on track and what you can do to improve your odds.
        </p>

        <div className="w-full max-w-3xl space-y-3 text-left">
          <Card className="ws-animate-fade-in">
            <CardContent>
              <p>We look at your goals and tell you if you are on track.</p>
            </CardContent>
          </Card>
          <Card className="ws-animate-fade-in ws-animate-stagger-1">
            <CardContent>
              <p>We predict how your investments might move and explain why in plain language.</p>
            </CardContent>
          </Card>
          <Card className="ws-animate-fade-in ws-animate-stagger-2">
            <CardContent>
              <p>We ran 1,000 possible futures so you can see your real odds before you make a decision.</p>
            </CardContent>
          </Card>
        </div>

        <div className="pt-1">
          <Link
            href="/onboarding"
            className="inline-flex min-h-11 min-w-44 cursor-pointer items-center justify-center rounded-md bg-ws-primary px-4 py-2 text-[14px] font-medium text-white transition-colors hover:bg-[#16243f]"
          >
            Get started free
          </Link>
        </div>

        <Card className="w-full max-w-xl">
          <CardHeader>
            <CardTitle>People using WealthSense</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-medium tabular-nums text-ws-primary">12,847</p>
            <p className="text-[#3d4558]">12,847 people are tracking their goals with WealthSense.</p>
          </CardContent>
        </Card>

        <div className="w-full max-w-xl">
          <Card>
            <CardHeader>
              <CardTitle>System status</CardTitle>
            </CardHeader>
            <CardContent className="text-left text-[#3d4558]">
              <p>Backend connection: {health ? "Connected" : "Unavailable"}</p>
              <p>Data mode: {health?.backend_mode ?? "unknown"}</p>
              <p>Environment: {health?.environment ?? "unknown"}</p>
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}
