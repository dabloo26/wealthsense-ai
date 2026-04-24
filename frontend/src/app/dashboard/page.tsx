"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { MessageCircle } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ASSETS } from "@/lib/assets";
import { loginDemo, streamCoachReply } from "@/lib/api";

type OnboardState = {
  goal?: string;
};

export default function DashboardPage() {
  const [coachOpen, setCoachOpen] = useState(false);
  const [authToken, setAuthToken] = useState("");
  const [coachInput, setCoachInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<Array<{ role: "user" | "coach"; text: string }>>([
    {
      role: "coach",
      text: "Hi there. I've looked at your plan. Want me to walk you through anything, or do you have a question?",
    },
  ]);
  const [profile] = useState<OnboardState>(() => {
    if (typeof window === "undefined") return {};
    const raw = window.localStorage.getItem("ws-onboarding");
    if (!raw) return {};
    try {
      return JSON.parse(raw) as OnboardState;
    } catch {
      return {};
    }
  });

  const topAssets = useMemo(() => ASSETS.slice(0, 3), []);

  useEffect(() => {
    let mounted = true;
    void loginDemo()
      .then((res) => {
        if (mounted) setAuthToken(res.access_token);
      })
      .catch(() => {
        if (mounted) setAuthToken("");
      });
    return () => {
      mounted = false;
    };
  }, []);

  const onAskCoach = async (e: FormEvent) => {
    e.preventDefault();
    const q = coachInput.trim();
    if (!q || !authToken || isStreaming) return;

    setMessages((prev) => [...prev, { role: "user", text: q }, { role: "coach", text: "" }]);
    setCoachInput("");
    setIsStreaming(true);
    try {
      await streamCoachReply(authToken, q, (chunk) => {
        setMessages((prev) => {
          const out = [...prev];
          const idx = out.length - 1;
          if (idx >= 0 && out[idx].role === "coach") {
            out[idx] = { ...out[idx], text: out[idx].text + chunk };
          }
          return out;
        });
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Coach is temporarily unavailable.";
      setMessages((prev) => {
        const out = [...prev];
        const idx = out.length - 1;
        if (idx >= 0 && out[idx].role === "coach") {
          out[idx] = { role: "coach", text: `I hit an issue: ${msg}` };
        }
        return out;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  return (
    <AppShell>
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <Card className="ws-animate-fade-in">
            <CardHeader>
              <CardTitle>Your goal snapshot</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p>
                You want to {profile.goal ?? "grow your wealth"}.
                <br />
                Based on your current plan, there is a 74% chance you get there.
              </p>
              <div className="h-3 rounded-full bg-[#e2e7f1]">
                <div className="ws-animate-progress h-3 rounded-full bg-ws-success" style={{ width: "74%" }} />
              </div>
              <Link href="/goals" className="text-ws-primary underline underline-offset-4">
                Want to improve your odds? See what helps
              </Link>
            </CardContent>
          </Card>

          <Card className="ws-animate-fade-in ws-animate-stagger-1">
            <CardHeader>
              <CardTitle>Your investments today</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {topAssets.map((asset) => (
                <Link key={asset.ticker} href={`/forecast/${asset.slug}`} className="ws-card p-4">
                  <p className="font-medium">{asset.name}</p>
                  <p className="text-[14px] text-[#3d4558]">Current price: ${(140 + topAssets.indexOf(asset) * 24.35).toFixed(2)}</p>
                  <p className="text-[14px] text-[#3d4558]">Our prediction: going up 4-11% in the next 30 days</p>
                  <div className="ws-mobile-scroll-hint mt-2 overflow-x-auto">
                    <svg width="220" height="48" viewBox="0 0 220 48" role="img" aria-label="Recent trend and likely range">
                      <polyline fill="none" stroke="#1b2b4b" strokeWidth="2" points="0,36 34,28 68,32 102,26 136,20 170,22 220,18" />
                      <rect x="150" y="10" width="70" height="24" fill="rgba(0,180,166,0.20)" />
                    </svg>
                  </div>
                  <p className="text-[14px] text-[#3d4558]">Driven mostly by strong recent momentum and low market fear right now.</p>
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>

        <aside className="hidden lg:block">
          <CoachPanel
            authReady={Boolean(authToken)}
            isStreaming={isStreaming}
            input={coachInput}
            setInput={setCoachInput}
            messages={messages}
            onAskCoach={onAskCoach}
          />
        </aside>
      </div>

      <button
        className="fixed bottom-5 right-5 z-30 flex min-h-11 min-w-11 items-center justify-center rounded-full bg-ws-primary p-3 text-white lg:hidden"
        onClick={() => setCoachOpen(true)}
        aria-label="Open coach"
      >
        <MessageCircle />
      </button>

      {coachOpen ? (
        <div className="fixed inset-0 z-40 bg-black/30 lg:hidden" onClick={() => setCoachOpen(false)}>
          <div className="absolute bottom-0 left-0 right-0 rounded-t-2xl bg-ws-surface p-4" onClick={(e) => e.stopPropagation()}>
            <CoachPanel
              authReady={Boolean(authToken)}
              isStreaming={isStreaming}
              input={coachInput}
              setInput={setCoachInput}
              messages={messages}
              onAskCoach={onAskCoach}
            />
            <div className="pt-3">
              <Button variant="outline" className="w-full" onClick={() => setCoachOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}

function CoachPanel({
  authReady,
  isStreaming,
  input,
  setInput,
  messages,
  onAskCoach,
}: {
  authReady: boolean;
  isStreaming: boolean;
  input: string;
  setInput: (v: string) => void;
  messages: Array<{ role: "user" | "coach"; text: string }>;
  onAskCoach: (e: FormEvent) => Promise<void>;
}) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>AI Coach</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="max-h-72 space-y-2 overflow-y-auto rounded-md border border-ws-border bg-[#f5f7fc] p-3">
          {messages.map((m, idx) => (
            <p key={`${m.role}-${idx}`} className="text-[14px]">
              <span className="font-medium">{m.role === "user" ? "You" : "Coach"}:</span>{" "}
              <span className={m.role === "coach" ? "text-[#3d4558]" : ""}>{m.text || (isStreaming ? "..." : "")}</span>
            </p>
          ))}
        </div>
        <form onSubmit={onAskCoach} className="space-y-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="h-11 w-full rounded-md border border-ws-border bg-ws-surface px-3 text-[14px]"
            placeholder="Ask me anything about your money..."
            disabled={!authReady || isStreaming}
          />
          <Button className="w-full" disabled={!authReady || isStreaming || !input.trim()}>
            {isStreaming ? "Thinking..." : "Send"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

