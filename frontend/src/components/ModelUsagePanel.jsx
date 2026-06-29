import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Card } from "./Card.jsx";

const COLORS = ["#6366f1", "#22d3ee", "#a78bfa", "#34d399", "#fbbf24", "#f87171"];

export function ModelUsagePanel({ summary, models }) {
  const usage = summary?.usage_by_model || {};
  const labelFor = (key) => models?.pool?.[key]?.label || key;
  const data = Object.entries(usage).map(([key, count]) => ({ name: labelFor(key), value: count }));

  return (
    <Card title="Model usage">
      {data.length === 0 ? (
        <div className="empty">No requests yet — try the playground.</div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={3}>
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="none" />
              ))}
            </Pie>
            <Tooltip contentStyle={{ background: "#121826", border: "1px solid #232c40", borderRadius: 10 }} />
            <Legend wrapperStyle={{ fontSize: 11, color: "#8b96ad" }} />
          </PieChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
