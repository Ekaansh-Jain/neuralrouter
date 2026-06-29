import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card } from "./Card.jsx";

const COLORS = { SIMPLE: "#34d399", MODERATE: "#fbbf24", COMPLEX: "#a78bfa" };
const ORDER = ["SIMPLE", "MODERATE", "COMPLEX"];

export function ComplexityPanel({ summary }) {
  const usage = summary?.usage_by_complexity || {};
  const data = ORDER.map((name) => ({ name, count: usage[name] || 0 }));
  const empty = data.every((d) => d.count === 0);

  return (
    <Card title="Complexity distribution">
      {empty ? (
        <div className="empty">No requests yet.</div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
            <XAxis dataKey="name" stroke="#5a647a" fontSize={12} />
            <YAxis stroke="#5a647a" fontSize={12} allowDecimals={false} />
            <Tooltip
              contentStyle={{ background: "#121826", border: "1px solid #232c40", borderRadius: 10 }}
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
            />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {data.map((d) => (
                <Cell key={d.name} fill={COLORS[d.name]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
