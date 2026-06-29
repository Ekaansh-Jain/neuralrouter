import { Card } from "./Card.jsx";

// Shows circuit-breaker state per model alongside the live fallback rate --
// the most telling operational signal for a routing gateway.
export function FallbackPanel({ summary }) {
  const breakers = summary?.circuit_breakers || [];
  const fallbackRate = summary?.fallback_rate ?? 0;
  const queueDepth = summary?.background_queue_depth ?? 0;
  const dropped = summary?.background_dropped ?? 0;

  return (
    <Card title="Resilience — circuit breakers">
      <div className="stats-line" style={{ marginBottom: 14 }}>
        <span>Fallback rate: <b>{(fallbackRate * 100).toFixed(1)}%</b></span>
        <span>Bg queue: <b>{queueDepth}</b></span>
        <span>Dropped: <b>{dropped}</b></span>
      </div>
      {breakers.length === 0 ? (
        <div className="empty">No breakers tracked yet — they appear once a model is used.</div>
      ) : (
        <div className="cb-list">
          {breakers.map((b) => (
            <div className="cb-row" key={b.model_key}>
              <span>{b.model_key}</span>
              <span>
                {b.consecutive_failures > 0 && (
                  <span className="footnote" style={{ marginRight: 10 }}>
                    {b.consecutive_failures} fail(s)
                  </span>
                )}
                <span className={`cb-state ${b.state}`}>{b.state}</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
