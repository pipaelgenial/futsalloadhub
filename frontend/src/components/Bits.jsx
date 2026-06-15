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
      <div className={`metric-num text-4xl md:text-5xl ${accent ? "text-[#CCFF00]" : "text-white"}`}>
        {value}
        {unit && <span className="text-base text-[#A3A3A3] ml-1 font-sans font-medium">{unit}</span>}
      </div>
    </div>
  );
}
