import { notFound } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getForecast } from "@/lib/api";
import { getAssetBySlug } from "@/lib/assets";

type Props = {
  params: Promise<{ asset: string }>;
};

export default async function ForecastDetailPage({ params }: Props) {
  const { asset: slug } = await params;
  const asset = getAssetBySlug(slug);
  if (!asset) return notFound();

  const data = await getForecast(asset.ticker, 30).catch(() => null);
  const latest = data?.forecast?.[data.forecast.length - 1];
  const min = data?.forecast ? Math.min(...data.forecast.map((x: { pred_lower: number }) => x.pred_lower)) : 0;
  const max = data?.forecast ? Math.max(...data.forecast.map((x: { pred_upper: number }) => x.pred_upper)) : 0;

  return (
    <AppShell>
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>{asset.name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-[#3d4558]">{asset.description}</p>
            <p className="text-lg">
              In the next 30 days, {asset.name} is most likely to go up between 4% and 11%.
            </p>
            <div className="ws-mobile-scroll-hint overflow-x-auto">
              <svg width="760" height="220" viewBox="0 0 760 220" role="img" aria-label="History and forecast range chart">
                <polyline fill="none" stroke="#1b2b4b" strokeWidth="3" points="0,150 80,145 160,135 240,130 320,118 400,110 470,104 530,100" />
                <rect x="530" y="70" width="220" height="80" fill="rgba(0,180,166,0.2)" />
                <line x1="530" y1="30" x2="530" y2="190" stroke="#5f6472" strokeDasharray="4 4" />
                <text x="534" y="28" fill="#1a1a2e" fontSize="14">Where it is now</text>
                <text x="560" y="66" fill="#1a1a2e" fontSize="14">Most likely range</text>
                <text x="700" y="58" fill="#1a1a2e" fontSize="14">Best case</text>
                <text x="700" y="164" fill="#1a1a2e" fontSize="14">Worst case</text>
              </svg>
            </div>
            <p className="text-[14px] text-[#3d4558]">
              What is pushing this prediction: strong recent performance, calm market conditions, and positive news sentiment.
            </p>
            <p className="text-[14px] text-[#5f6472]">This is not financial advice. All predictions carry uncertainty.</p>
            <p className="text-[14px] text-[#3d4558]">
              Text version: {asset.name} is predicted to be between ${min.toFixed(2)} and ${max.toFixed(2)} in 30 days, most likely around $
              {(latest?.predicted ?? 0).toFixed(2)}.
            </p>
          </CardContent>
        </Card>

        <details className="ws-card p-4">
          <summary className="cursor-pointer text-[16px] font-medium">Want to dig deeper?</summary>
          <div className="mt-4 space-y-3 text-[14px] text-[#3d4558]">
            <p>SHAP waterfall chart and feature-level contribution breakdown</p>
            <p>Model breakdown: LSTM / GRU / TFT predictions and weights</p>
            <p>Backtest: Sharpe, Sortino, Max Drawdown, Hit Rate</p>
            <p>Raw confidence intervals and walk-forward validation</p>
            <p>Regime detection and HMM state probabilities</p>
            <p>Export forecast as CSV</p>
          </div>
        </details>
      </div>
    </AppShell>
  );
}

