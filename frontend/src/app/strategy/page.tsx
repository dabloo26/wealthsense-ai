"use client";

import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const scenarios = [
  {
    icon: "📉",
    title: "What if the market crashes like 2008?",
    description: "A severe downturn with sharp losses and a slower recovery.",
    result: "In a 2008-style crash, your investments would likely drop about 38% at the worst point. They would recover in about 3.5 years.",
  },
  {
    icon: "📈",
    title: "What if we have a bull run like 2017?",
    description: "A strong growth period with broad gains.",
    result: "In a strong growth period, your investments could climb quickly and improve your goal odds by about 10 points.",
  },
  {
    icon: "😷",
    title: "What if there's another pandemic?",
    description: "A sudden shock followed by uneven recovery.",
    result: "In a pandemic-style shock, you could see a fast drop, with recovery likely taking around 18-24 months.",
  },
  {
    icon: "💸",
    title: "What if inflation stays high for 5 more years?",
    description: "Higher costs reduce real purchasing power.",
    result: "If inflation stays high, your plan may need higher monthly savings to stay on track.",
  },
  {
    icon: "➕",
    title: "Build my own scenario",
    description: "Set your own assumptions and test them.",
    result: "Your custom scenario will estimate likely drop, recovery time, and effect on goal success.",
  },
];

export default function StrategyPage() {
  const [selected, setSelected] = useState(0);

  return (
    <AppShell>
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>What if things were different?</CardTitle>
          </CardHeader>
          <CardContent>
            <p>Test your plan against different situations.</p>
          </CardContent>
        </Card>

        <div className="grid gap-3 md:grid-cols-2">
          {scenarios.map((scenario, idx) => (
            <button
              key={scenario.title}
              type="button"
              onClick={() => setSelected(idx)}
              className={`ws-card cursor-pointer p-4 text-left ${selected === idx ? "border-ws-accent" : ""}`}
            >
              <p className="text-2xl">{scenario.icon}</p>
              <p className="font-medium">{scenario.title}</p>
              <p className="text-[14px] text-[#3d4558]">{scenario.description}</p>
            </button>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Scenario outcome</CardTitle>
          </CardHeader>
          <CardContent>
            <p>{scenarios[selected].result}</p>
          </CardContent>
        </Card>

        <details className="ws-card p-4">
          <summary className="cursor-pointer font-medium">Advanced</summary>
          <div className="mt-3 space-y-2 text-[14px] text-[#3d4558]">
            <p>Custom parameter editor</p>
            <p>Raw backtest metrics</p>
            <p>Strategy comparison table</p>
          </div>
        </details>
      </div>
    </AppShell>
  );
}

