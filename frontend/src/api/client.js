// Thin API client for the NeuralRouter backend.
const BASE_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export const api = {
  baseUrl: BASE_URL,
  chat: (query) => request("/v1/chat", { method: "POST", body: JSON.stringify({ query }) }),
  summary: () => request("/metrics/summary"),
  recent: (limit = 50) => request(`/metrics/recent?limit=${limit}`),
  models: () => request("/metrics/models"),
  health: () => request("/health"),
};
