"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ASSETS, bestAssetForGoal } from "@/lib/assets";

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [goal, setGoal] = useState("Grow my wealth");
  const [customGoal, setCustomGoal] = useState("");
  const [riskMood, setRiskMood] = useState("A little worried but I could wait it out");
  const [assetTicker, setAssetTicker] = useState(bestAssetForGoal(goal).ticker);
  const [loading, setLoading] = useState(false);

  const progress = (step / 3) * 100;
  const selectedGoal = customGoal.trim() ? customGoal.trim() : goal;

  const applyGoal = (newGoal: string) => {
    setGoal(newGoal);
    setAssetTicker(bestAssetForGoal(newGoal).ticker);
  };

  const finish = () => {
    setLoading(true);
    window.setTimeout(() => {
      const payload = {
        goal: selectedGoal,
        riskMood,
        assetTicker,
      };
      localStorage.setItem("ws-onboarding", JSON.stringify(payload));
      router.push("/dashboard");
    }, 1400);
  };

  return (
    <AppShell>
      <Card className="mx-auto max-w-3xl">
        <CardHeader>
          <CardTitle>3-step onboarding</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-[14px] text-[#3d4558]">
              <span>Step {step} of 3</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-2 rounded-full bg-[#e2e7f1]">
              <div className="ws-animate-progress h-2 rounded-full bg-ws-accent" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {step === 1 ? (
            <div className="space-y-4">
              <p className="text-lg font-medium">What are you saving for?</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { emoji: "🏠", label: "Buy a home" },
                  { emoji: "☀️", label: "Retire comfortably" },
                  { emoji: "🛡️", label: "Build a safety net" },
                  { emoji: "📈", label: "Grow my wealth" },
                ].map((item) => (
                  <label key={item.label} className={`ws-card block cursor-pointer p-4 text-left ${goal === item.label ? "border-ws-accent" : ""}`}>
                    <input
                      type="radio"
                      name="goal"
                      value={item.label}
                      checked={goal === item.label}
                      onChange={(e) => applyGoal(e.target.value)}
                      className="sr-only"
                    />
                    <p className="text-2xl">{item.emoji}</p>
                    <p className="mt-2 font-medium">{item.label}</p>
                  </label>
                ))}
              </div>
              <div>
                <label htmlFor="custom-goal" className="mb-2 block text-[14px] text-[#3d4558]">
                  Something else — tell us
                </label>
                <Input id="custom-goal" value={customGoal} onChange={(e) => setCustomGoal(e.target.value)} />
              </div>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="space-y-4">
              <p className="text-lg font-medium">How would you feel if your investment dropped 20% next month?</p>
              <div className="space-y-3">
                {[
                  "Very stressed — I want to keep my money safe",
                  "A little worried but I could wait it out",
                  "Fine — I know it'll recover, I'm in it for the long run",
                ].map((item, idx) => (
                  <label key={item} className={`ws-card flex w-full cursor-pointer items-start gap-3 p-4 text-left ${riskMood === item ? "border-ws-accent" : ""}`}>
                    <input
                      type="radio"
                      name="riskMood"
                      value={item}
                      checked={riskMood === item}
                      onChange={(e) => setRiskMood(e.target.value)}
                      className="sr-only"
                    />
                    <span>{idx === 0 ? "😰" : idx === 1 ? "😐" : "😎"}</span>
                    <span>{item}</span>
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          {step === 3 ? (
            <div className="space-y-4">
              <p className="text-lg font-medium">Pick something to watch first</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {ASSETS.map((asset) => (
                  <label
                    key={asset.ticker}
                    className={`ws-card block cursor-pointer p-4 text-left ${assetTicker === asset.ticker ? "border-ws-accent" : ""}`}
                  >
                    <input
                      type="radio"
                      name="assetTicker"
                      value={asset.ticker}
                      checked={assetTicker === asset.ticker}
                      onChange={(e) => setAssetTicker(e.target.value)}
                      className="sr-only"
                    />
                    <p className="font-medium">{asset.name}</p>
                    <p className="text-[14px] text-[#3d4558]">{asset.description}</p>
                    <p className="mt-2 text-[14px] text-ws-primary">{asset.riskLabel}</p>
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex items-center justify-between">
            <Button variant="outline" onClick={() => setStep((s) => Math.max(1, s - 1))}>
              Back
            </Button>
            {step < 3 ? (
              <Button onClick={() => setStep((s) => Math.min(3, s + 1))}>Continue</Button>
            ) : (
              <Button onClick={finish}>Finish</Button>
            )}
          </div>

          {loading ? (
            <div className="ws-card p-4 text-center">
              <p>Setting up your personal forecast... this takes about 10 seconds</p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </AppShell>
  );
}

