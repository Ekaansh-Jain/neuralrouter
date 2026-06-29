import { useCallback } from "react";
import { api } from "./api/client.js";
import { usePolling } from "./hooks/usePolling.js";
import { Header } from "./components/Header.jsx";
import { StatCards } from "./components/StatCards.jsx";
import { Playground } from "./components/Playground.jsx";
import { LatencyPanel } from "./components/LatencyPanel.jsx";
import { ModelUsagePanel } from "./components/ModelUsagePanel.jsx";
import { ComplexityPanel } from "./components/ComplexityPanel.jsx";
import { CostPanel } from "./components/CostPanel.jsx";
import { FallbackPanel } from "./components/FallbackPanel.jsx";

export default function App() {
  const { data: summary, error: summaryError, refresh: refreshSummary } = usePolling(api.summary, 3000);
  const { data: recent, refresh: refreshRecent } = usePolling(() => api.recent(100), 3000);
  const { data: health } = usePolling(api.health, 10000);
  // Model metadata changes rarely; poll slowly.
  const { data: models } = usePolling(api.models, 60000);

  const connected = !summaryError;

  const handleResponse = useCallback(() => {
    // Refresh charts immediately after a manual request instead of waiting.
    refreshSummary();
    refreshRecent();
  }, [refreshSummary, refreshRecent]);

  return (
    <div className="app">
      <Header health={health} connected={connected} />

      {summaryError && (
        <div className="error-banner">
          Can’t reach the backend at <b>{api.baseUrl}</b>. Start it with{" "}
          <code>uvicorn app.main:app</code> (or set <code>VITE_API_URL</code>). · {summaryError}
        </div>
      )}

      <StatCards summary={summary} />

      <div className="grid main-grid" style={{ marginTop: 18 }}>
        <Playground onResponse={handleResponse} />
        <FallbackPanel summary={summary} />
      </div>

      <div className="section-title">Observability</div>
      <div className="grid charts-grid">
        <LatencyPanel summary={summary} />
        <ModelUsagePanel summary={summary} models={models} />
        <ComplexityPanel summary={summary} />
        <CostPanel recent={recent} />
      </div>
    </div>
  );
}
