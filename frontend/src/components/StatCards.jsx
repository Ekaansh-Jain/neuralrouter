import { Card } from "./Card.jsx";

function Stat({ value, label, sub }) {
  return (
    <Card className="stat">
      <span className="value">{value}</span>
      <span className="label">{label}</span>
      {sub && <span className="sub">{sub}</span>}
    </Card>
  );
}

export function StatCards({ summary }) {
  const s = summary || {};
  const pct = (x) => (x != null ? `${(x * 100).toFixed(1)}%` : "—");
  const cost = s.modeled_cost_usd_total ?? 0;

  return (
    <div className="grid stat-grid">
      <Stat value={s.total_requests ?? 0} label="Total requests" />
      <Stat value={pct(s.success_rate)} label="Success rate" />
      <Stat value={`${s.latency_ms?.p95 ?? 0} ms`} label="Latency p95" sub={`p50 ${s.latency_ms?.p50 ?? 0} · p99 ${s.latency_ms?.p99 ?? 0}`} />
      <Stat value={pct(s.fallback_rate)} label="Fallback rate" />
      <Stat value={pct(s.cache_hit_rate)} label="Cache hit rate" />
      <Stat value={`$${cost.toFixed(6)}`} label="Modeled cost" sub={`${s.tokens_total ?? 0} tokens`} />
    </div>
  );
}
