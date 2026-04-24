"use client";

import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ASSETS } from "@/lib/assets";

export default function ForecastPage() {
  return (
    <AppShell>
      <Card>
        <CardHeader>
          <CardTitle>Forecasts</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-[#3d4558]">Pick an asset to see the full forecast detail.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {ASSETS.map((asset) => (
              <Link key={asset.ticker} href={`/forecast/${asset.slug}`} className="ws-card p-4">
                <p className="font-medium">{asset.name}</p>
                <p className="text-[14px] text-[#3d4558]">{asset.description}</p>
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </AppShell>
  );
}

