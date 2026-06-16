export function riskMeta(risk) {
  switch (risk) {
    case "safe":
      return { label: "Ótimo", color: "#00E676", bg: "rgba(0,230,118,0.1)", border: "rgba(0,230,118,0.3)" };
    case "warning":
      return { label: "Atenção", color: "#FFEA00", bg: "rgba(255,234,0,0.1)", border: "rgba(255,234,0,0.3)" };
    case "danger":
      return { label: "Risco Elevado", color: "#FF3B30", bg: "rgba(255,59,48,0.1)", border: "rgba(255,59,48,0.3)" };
    case "insufficient":
      return { label: "Dados Insuficientes", color: "#A3A3A3", bg: "rgba(163,163,163,0.08)", border: "rgba(163,163,163,0.2)" };
    case "low":
      return { label: "Baixa Carga", color: "#A3A3A3", bg: "rgba(163,163,163,0.08)", border: "rgba(163,163,163,0.2)" };
    default:
      return { label: "Sem Dados", color: "#525252", bg: "rgba(82,82,82,0.1)", border: "rgba(82,82,82,0.2)" };
  }
}

export function zoneColor(zone) {
  // Color per zone matching domain (Monotonia/Strain/ACWR)
  const map = {
    // Monotonia
    high_variation: "#00E676",
    ideal: "#00E676",
    moderate_high: "#FFEA00",
    critical: "#FF3B30",
    // Strain
    low: "#A3A3A3",
    moderate: "#00E676",
    elevated: "#FFEA00",
    extreme: "#FF3B30",
    // ACWR
    detraining: "#FFEA00",
    sweet_spot: "#00E676",
    alert: "#FFEA00",
    high_risk: "#FF3B30",
    no_data: "#525252",
  };
  return map[zone] || "#A3A3A3";
}

export function RiskBadge({ risk, testid }) {
  const m = riskMeta(risk);
  return (
    <span
      data-testid={testid}
      className="font-head text-xs tracking-widest px-2.5 py-1 inline-block uppercase"
      style={{ color: m.color, background: m.bg, border: `1px solid ${m.border}` }}
    >
      {m.label}
    </span>
  );
}

export function MetricCard({ label, value, unit, accent = false, testid, zoneCol }) {
  return (
    <div className="fld-card relative overflow-hidden" data-testid={testid}>
      {zoneCol && (
        <div className="absolute top-0 left-0 w-1 h-full" style={{ background: zoneCol }} />
      )}
      <div className="fld-label">{label}</div>
      <div className={`metric-num text-2xl sm:text-3xl md:text-4xl ${accent ? "text-[#CCFF00]" : "text-white"}`}>
        {value}
        {unit && <span className="text-xs sm:text-sm text-[#A3A3A3] ml-1 font-sans font-medium">{unit}</span>}
      </div>
    </div>
  );
}

export const SESSION_TYPES = {
  training: { label: "Treino", short: "T", color: "#CCFF00", emoji: "" },
  match: { label: "Jogo", short: "J", color: "#FF3B30", emoji: "" },
  gym: { label: "Ginásio", short: "G", color: "#FFEA00", emoji: "" },
  recovery: { label: "Recuperação", short: "R", color: "#00B0FF", emoji: "" },
};

export const SESSION_TYPE_ORDER = ["training", "match", "gym", "recovery"];

export function SessionTypeBadge({ type, size = "md", testid }) {
  const meta = SESSION_TYPES[type] || SESSION_TYPES.training;
  const sizeCls = size === "sm" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1";
  return (
    <span
      data-testid={testid}
      className={`font-head uppercase tracking-widest inline-block ${sizeCls}`}
      style={{
        color: meta.color,
        background: `${meta.color}15`,
        border: `1px solid ${meta.color}50`,
      }}
    >
      {meta.label}
    </span>
  );
}

export const MONOTONY_ZONES = {
  high_variation: { label: "Boa variação", color: "#00E676", message: "Boa variação entre sessões — adaptação física favorecida." },
  ideal: { label: "Ideal", color: "#00E676", message: "Monotonia em zona ideal (1.0–1.5) — cargas bem distribuídas." },
  moderate_high: { label: "Moderada-Alta", color: "#FFEA00", message: "Monotonia moderada-alta (1.5–2.0) — treinos pouco variados, intercalar intensidades." },
  critical: { label: "Crítica", color: "#FF3B30", message: "Monotonia crítica (>2.0) — risco elevado de overtraining e lesão. Introduzir sessões de baixa intensidade." },
  no_data: { label: "Sem dados", color: "#A3A3A3", message: "Sem dados suficientes." },
};

export function MonotonyAlert({ value, zone, compact = false, testid }) {
  const meta = MONOTONY_ZONES[zone] || MONOTONY_ZONES.no_data;
  if (compact) {
    return (
      <div
        className="flex items-center gap-2 text-xs"
        style={{ color: meta.color }}
        data-testid={testid}
      >
        <span className="w-2 h-2 rounded-full inline-block" style={{ background: meta.color }} />
        <span className="font-head uppercase tracking-widest">{meta.label}</span>
        {value > 0 && <span className="metric-num text-white">{value}</span>}
      </div>
    );
  }
  return (
    <div
      className="fld-card flex items-start gap-4"
      style={{ borderLeft: `4px solid ${meta.color}` }}
      data-testid={testid}
    >
      <div>
        <div className="fld-label">Monotonia da Equipa</div>
        <div className="flex items-baseline gap-3 mt-1">
          <div className="metric-num text-4xl" style={{ color: meta.color }}>{value || "—"}</div>
          <div className="font-head text-base uppercase tracking-widest" style={{ color: meta.color }}>{meta.label}</div>
        </div>
        <p className="text-xs text-[#A3A3A3] mt-2 max-w-md">{meta.message}</p>
      </div>
    </div>
  );
}
