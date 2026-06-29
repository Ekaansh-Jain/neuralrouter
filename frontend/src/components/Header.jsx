export function Header({ health, connected }) {
  return (
    <header className="header">
      <div className="brand">
        <div className="logo">N</div>
        <div>
          <h1>NeuralRouter</h1>
          <p>Intelligent LLM routing gateway · complexity-aware · self-healing</p>
        </div>
      </div>
      <div className="header-right">
        {health?.provider_mode && (
          <span className="badge">mode: {health.provider_mode}</span>
        )}
        {health?.tokenizer && (
          <span className="badge">tok: {health.tokenizer}</span>
        )}
        <span className={`badge ${connected ? "live" : "offline"}`}>
          <span className="dot" />
          {connected ? "live" : "disconnected"}
        </span>
      </div>
    </header>
  );
}
