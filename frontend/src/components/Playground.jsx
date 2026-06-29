import { useState } from "react";
import { Card } from "./Card.jsx";
import { api } from "../api/client.js";

const EXAMPLES = [
  "What is the capital of France?",
  "Summarize the plot of Hamlet in two sentences.",
  "Design a fault-tolerant async pipeline and explain the trade-offs, then compare two approaches step by step.",
];

export function Playground({ onResponse }) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState(null);
  const [error, setError] = useState(null);

  async function send() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.chat(query);
      setResp(result);
      onResponse?.(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card title="Playground" className="playground">
      <textarea
        value={query}
        placeholder="Ask anything — NeuralRouter will classify and route it…"
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
        }}
      />
      <div className="row">
        <button className="primary" onClick={send} disabled={loading || !query.trim()}>
          {loading ? "Routing…" : "Send  ⌘↵"}
        </button>
        <div className="examples">
          {EXAMPLES.map((ex, i) => (
            <span key={i} className="chip" onClick={() => setQuery(ex)}>
              {ex.length > 38 ? ex.slice(0, 38) + "…" : ex}
            </span>
          ))}
        </div>
      </div>

      {error && <div className="error-banner" style={{ marginTop: 14 }}>{error}</div>}

      {resp && <ResponseView resp={resp} />}
    </Card>
  );
}

function ResponseView({ resp }) {
  return (
    <div className="answer">
      <div className="meta">
        <span className={`pill ${resp.complexity}`}>
          {resp.complexity} · {(resp.confidence * 100).toFixed(0)}%
        </span>
        {resp.chosen_model_label && (
          <span className="pill model">{resp.chosen_model_label}</span>
        )}
        {resp.fallback_occurred && <span className="pill fallback">fallback</span>}
        {resp.cache_hit && <span className="pill cache">cache hit</span>}
      </div>

      <div className="text">{resp.answer || resp.error || "(no answer)"}</div>

      <div className="stats-line">
        <span>⏱ {resp.latency_ms} ms</span>
        <span>🎟 {resp.prompt_tokens + resp.completion_tokens} tokens</span>
        <span>💲 ${resp.modeled_cost_usd.toFixed(6)}</span>
        <span>🔁 {resp.attempts.length} attempt(s)</span>
      </div>

      {resp.attempts.length > 1 && (
        <div className="footnote">
          Route: {resp.attempts.map((a) => `${a.model_key}${a.ok ? " ✓" : ` ✗(${a.error_category || a.detail || "fail"})`}`).join("  →  ")}
        </div>
      )}
    </div>
  );
}
