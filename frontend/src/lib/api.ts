const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function getHealth() {
  const resp = await fetch(`${API_BASE}/health`, { cache: "no-store" });
  if (!resp.ok) throw new Error("Health check failed");
  return resp.json();
}

export async function getForecast(ticker: string, horizonDays: number) {
  const resp = await fetch(`${API_BASE}/forecast`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, horizon_days: horizonDays }),
  });
  if (!resp.ok) throw new Error("Forecast failed");
  return resp.json();
}

export async function getForecastDetail(ticker: string, horizonDays: number) {
  const resp = await fetch(`${API_BASE}/forecast-detail/${ticker}?horizon_days=${horizonDays}`, { cache: "no-store" });
  if (!resp.ok) throw new Error("Forecast detail failed");
  return resp.json();
}

export async function loginDemo(email = "demo@wealthsense.ai", name = "Demo User") {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, name }),
  });
  if (!resp.ok) throw new Error("Login failed");
  return resp.json() as Promise<{ access_token: string }>;
}

export async function streamCoachReply(
  token: string,
  question: string,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const url = `${API_BASE}/coach/stream?question=${encodeURIComponent(question)}`;
  const resp = await fetch(url, {
    method: "GET",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok || !resp.body) {
    const text = await resp.text();
    throw new Error(text || "Coach request failed");
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data !== "[DONE]") onChunk(data);
      }
    }
  }
}

