import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card } from "./Card.jsx";

const COLORS = ["#34d399", "#fbbf24", "#f87171"];

export function LatencyPanel({ summary }) {
  const l = summary?.latency_ms || {};
  const data = [
    { name: "p50", ms: l.p50 ?? 0 },
    { name: "p95", ms: l.p95 ?? 0 },
    { name: "p99", ms: l.p99 ?? 0 },
  ];

  return (
    <Card title="Latency percentiles (ms)">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <XAxis dataKey="name" stroke="#5a647a" fontSize={12} />
          <YAxis stroke="#5a647a" fontSize={12} />
          <Tooltip
            contentStyle={{ background: "#121826", border: "1px solid #232c40", borderRadius: 10 }}
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
          />
          <Bar dataKey="ms" radius={[6, 6, 0, 0]}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
