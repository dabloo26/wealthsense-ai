export type AssetItem = {
  ticker: string;
  slug: string;
  name: string;
  description: string;
  riskLabel: "Steady" | "Moderate" | "Higher risk";
};

export const ASSETS: AssetItem[] = [
  { ticker: "AAPL", slug: "apple", name: "Apple", description: "The world's most valuable company. Makes iPhones and Macs.", riskLabel: "Moderate" },
  { ticker: "MSFT", slug: "microsoft", name: "Microsoft", description: "A global software leader behind Windows, Office, and Azure cloud.", riskLabel: "Steady" },
  { ticker: "NVDA", slug: "nvidia", name: "NVIDIA", description: "A chip leader powering AI and high-performance computing.", riskLabel: "Higher risk" },
  { ticker: "TSLA", slug: "tesla", name: "Tesla", description: "An electric vehicle and energy company with rapid growth swings.", riskLabel: "Higher risk" },
  { ticker: "SPY", slug: "sp500-etf", name: "S&P 500 ETF", description: "Tracks 500 large U.S. companies for broad market exposure.", riskLabel: "Steady" },
  { ticker: "QQQ", slug: "nasdaq-100-etf", name: "Nasdaq 100 ETF", description: "Focuses on large tech and innovation-driven companies.", riskLabel: "Moderate" },
  { ticker: "VOO", slug: "vanguard-500-etf", name: "Vanguard 500 ETF", description: "Low-cost exposure to major U.S. businesses.", riskLabel: "Steady" },
  { ticker: "AMZN", slug: "amazon", name: "Amazon", description: "Global e-commerce and cloud infrastructure giant.", riskLabel: "Moderate" },
  { ticker: "GOOGL", slug: "alphabet", name: "Alphabet", description: "Google's parent company with search, ads, and AI products.", riskLabel: "Moderate" },
  { ticker: "META", slug: "meta", name: "Meta", description: "Runs Facebook, Instagram, and messaging apps used worldwide.", riskLabel: "Higher risk" },
];

export function bestAssetForGoal(goal: string): AssetItem {
  const normalized = goal.toLowerCase();
  if (normalized.includes("home") || normalized.includes("safety")) return ASSETS.find((a) => a.ticker === "VOO") ?? ASSETS[0];
  if (normalized.includes("retire")) return ASSETS.find((a) => a.ticker === "SPY") ?? ASSETS[0];
  return ASSETS.find((a) => a.ticker === "QQQ") ?? ASSETS[0];
}

export function getAssetBySlug(slug: string): AssetItem | undefined {
  return ASSETS.find((asset) => asset.slug === slug);
}

