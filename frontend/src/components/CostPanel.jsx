import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { Card } from "./Card.jsx";

// Builds a cumulative modeled-cost curve from the recent request feed.
export function CostPanel({ recent }) {
  const items = (recent?.items || []).slice().reverse(); // oldest -> newest
  let cumulative = 0;
  const data = items.map((it, i) => {
    cumulative += it.cost_usd || 0;
    return { i: i + 1, cost: Number(cumulative.toFixed(6)) };
  });

  return (
    <Card title="Cumulative modeled cost (USD)">
      {data.length === 0 ? (
        <div className="empty">No requests yet.</div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="i" stroke="#5a647a" fontSize={11} />
              <YAxis stroke="#5a647a" fontSize={11} width={70} />
              <Tooltip contentStyle={{ background: "#121826", border: "1px solid #232c40", borderRadius: 10 }} />
              <Area type="monotone" dataKey="cost" stroke="#22d3ee" strokeWidth={2} fill="url(#costGrad)" />
            </AreaChart>
          </ResponsiveContainer>
          <div className="footnote">Modeled at provider list prices — actual free-tier spend is $0.</div>
        </>
      )}
    </Card>
  );
}
