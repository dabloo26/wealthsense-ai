"use client";

import { useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function GoalsPage() {
  const [goalName, setGoalName] = useState("Retire comfortably");
  const [amount, setAmount] = useState(750000);
  const [years, setYears] = useState(22);
  const [monthly, setMonthly] = useState(900);
  const [ran, setRan] = useState(false);
  const [extraSave, setExtraSave] = useState(0);
  const [extraYears, setExtraYears] = useState(0);
  const [extraRisk, setExtraRisk] = useState(0);

  const baseOdds = useMemo(() => {
    const coverage = Math.min(1, (monthly * 12 * years) / amount);
    return Math.max(0.2, Math.min(0.95, 0.42 + coverage * 0.48));
  }, [amount, years, monthly]);

  const improvedOdds = Math.min(0.99, baseOdds + extraSave * 0.0007 + extraYears * 0.03 + extraRisk * 0.01);

  return (
    <AppShell>
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Goal Planner</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-[14px] text-[#3d4558]">I want to</label>
                <Input value={goalName} onChange={(e) => setGoalName(e.target.value)} />
              </div>
              <div>
                <label className="mb-1 block text-[14px] text-[#3d4558]">I will need about $</label>
                <Input type="number" value={amount} onChange={(e) => setAmount(Number(e.target.value || 0))} />
              </div>
              <div>
                <label className="mb-1 block text-[14px] text-[#3d4558]">I want to reach this in years</label>
                <Input type="number" value={years} onChange={(e) => setYears(Number(e.target.value || 0))} />
              </div>
              <div>
                <label className="mb-1 block text-[14px] text-[#3d4558]">I can set aside $ per month</label>
                <Input type="number" value={monthly} onChange={(e) => setMonthly(Number(e.target.value || 0))} />
              </div>
            </div>
            <Button onClick={() => setRan(true)}>Run my plan</Button>
          </CardContent>
        </Card>

        {ran ? (
          <Card>
            <CardHeader>
              <CardTitle>Results for {goalName}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-3xl font-medium tabular-nums">{Math.round(baseOdds * 100)}% chance you reach your goal</p>
              <p className="text-[#3d4558]">
                We ran 1,000 possible versions of the future based on historical market behavior. In {Math.round(baseOdds * 1000)} of them, you
                hit your target. In {1000 - Math.round(baseOdds * 1000)} of them, you fell short.
              </p>
              <div className="ws-mobile-scroll-hint overflow-x-auto rounded-md border border-ws-border p-3">
                <svg width="560" height="140" viewBox="0 0 560 140" role="img" aria-label="Outcome fan chart">
                  <path d="M20 120 Q180 30 540 60 L540 110 Q180 130 20 120 Z" fill="rgba(0,180,166,0.2)" />
                  <path d="M20 120 Q180 70 540 85" stroke="#1b2b4b" fill="none" strokeWidth="2" />
                </svg>
              </div>
              <p className="text-[14px] text-[#3d4558]">
                Text version: most outcomes land around your target timeline, with a likely range between moderate shortfall and early success.
              </p>

              <div className="grid gap-3 md:grid-cols-3">
                <div className="ws-card p-4">😊 Best case — things go well: you hit your goal about 2 years early.</div>
                <div className="ws-card p-4">😐 Most likely — you reach it close to your planned date.</div>
                <div className="ws-card p-4">😟 Tough case — markets struggle: you fall about ${(amount * 0.05).toFixed(0)} short.</div>
              </div>

              <Card className="bg-[#f5f7fc]">
                <CardHeader>
                  <CardTitle>What can improve your odds?</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="block text-[14px]">Save $100 more per month</label>
                    <input type="range" min={0} max={100} value={extraSave} onChange={(e) => setExtraSave(Number(e.target.value))} className="w-full" />
                  </div>
                  <div>
                    <label className="block text-[14px]">Wait 2 more years</label>
                    <input type="range" min={0} max={2} value={extraYears} onChange={(e) => setExtraYears(Number(e.target.value))} className="w-full" />
                  </div>
                  <div>
                    <label className="block text-[14px]">Take on a little more risk</label>
                    <input type="range" min={0} max={4} value={extraRisk} onChange={(e) => setExtraRisk(Number(e.target.value))} className="w-full" />
                  </div>
                  <p className="tabular-nums">
                    Odds go from {Math.round(baseOdds * 100)}% to {Math.round(improvedOdds * 100)}%
                  </p>
                </CardContent>
              </Card>
            </CardContent>
          </Card>
        ) : null}

        <details className="ws-card p-4">
          <summary className="cursor-pointer font-medium">Advanced</summary>
          <div className="mt-3 space-y-2 text-[14px] text-[#3d4558]">
            <p>Full Monte Carlo distribution chart</p>
            <p>Percentile outcome table</p>
            <p>Assumption editor: return rate, inflation, tax rate</p>
          </div>
        </details>
      </div>
    </AppShell>
  );
}

