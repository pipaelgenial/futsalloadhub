import { useEffect, useState } from "react";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { RiskBadge } from "@/components/Bits";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea, CartesianGrid,
} from "recharts";

const A1_COLOR = "#CCFF00";
const A2_COLOR = "#FF3B30";

function MetricRow({ label, v1, v2, unit, highlight }) {
  const left = parseFloat(v1) || 0;
  const right = parseFloat(v2) || 0;
  const lWin = highlight === "lower" ? left < right : left > right;
  const rWin = highlight === "lower" ? right < left : right > left;
  return (
    <div className="grid grid-cols-3 items-center py-3 border-b border-white/5">
      <div className="metric-num text-2xl text-left" style={{ color: lWin ? A1_COLOR : "#fff" }}>{v1}{unit && <span className="text-xs text-[#A3A3A3] ml-1 font-sans">{unit}</span>}</div>
      <div className="text-center text-xs uppercase tracking-widest text-[#525252]">{label}</div>
      <div className="metric-num text-2xl text-right" style={{ color: rWin ? A1_COLOR : "#fff" }}>{v2}{unit && <span className="text-xs text-[#A3A3A3] ml-1 font-sans">{unit}</span>}</div>
    </div>
  );
}

export default function Compare() {
  const [athletes, setAthletes] = useState([]);
  const [a1, setA1] = useState("");
  const [a2, setA2] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await http.get("/athletes");
        setAthletes(data);
        if (data[0]) setA1(data[0].id);
        if (data[1]) setA2(data[1].id);
      } catch (err) { toast.error(formatApiError(err)); }
    })();
  }, []);

  useEffect(() => {
    if (!a1 || !a2 || a1 === a2) { setData(null); return; }
    (async () => {
      setLoading(true);
      try {
        const { data } = await http.get(`/analytics/compare?a1=${a1}&a2=${a2}`);
        setData(data);
      } catch (err) { toast.error(formatApiError(err)); }
      finally { setLoading(false); }
    })();
  }, [a1, a2]);

  return (
    <div className="space-y-8">
      <div>
        <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Comparação</div>
        <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">COMPARAR ATLETAS</h1>
      </div>

      {/* Pickers */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="fld-card border-l-4" style={{ borderLeftColor: A1_COLOR }}>
          <div className="fld-label">Atleta 1</div>
          <select className="fld-input mt-2" value={a1} onChange={(e) => setA1(e.target.value)} data-testid="compare-a1">
            {athletes.map((a) => (<option key={a.id} value={a.id}>{a.name}</option>))}
          </select>
        </div>
        <div className="fld-card border-l-4" style={{ borderLeftColor: A2_COLOR }}>
          <div className="fld-label">Atleta 2</div>
          <select className="fld-input mt-2" value={a2} onChange={(e) => setA2(e.target.value)} data-testid="compare-a2">
            {athletes.map((a) => (<option key={a.id} value={a.id}>{a.name}</option>))}
          </select>
        </div>
      </div>

      {a1 === a2 && a1 && (
        <div className="fld-card text-[#FFEA00]">⚠ Selecione dois atletas diferentes.</div>
      )}

      {loading && <div className="text-[#A3A3A3] font-head tracking-widest">A CARREGAR...</div>}

      {data && !loading && (
        <>
          {/* Header row */}
          <div className="grid grid-cols-3 items-center gap-4" data-testid="compare-headers">
            <div className="text-left">
              <div className="text-xs uppercase tracking-widest" style={{ color: A1_COLOR }}>Atleta 1</div>
              <div className="font-head text-3xl font-bold mt-1">{data.a1.athlete.name}</div>
              <div className="text-xs text-[#A3A3A3]">{data.a1.athlete.position}</div>
              <div className="mt-3"><RiskBadge risk={data.a1.metrics.risk} /></div>
            </div>
            <div className="text-center">
              <div className="font-head text-7xl text-[#525252] font-black">VS</div>
            </div>
            <div className="text-right">
              <div className="text-xs uppercase tracking-widest" style={{ color: A2_COLOR }}>Atleta 2</div>
              <div className="font-head text-3xl font-bold mt-1">{data.a2.athlete.name}</div>
              <div className="text-xs text-[#A3A3A3]">{data.a2.athlete.position}</div>
              <div className="mt-3 flex justify-end"><RiskBadge risk={data.a2.metrics.risk} /></div>
            </div>
          </div>

          {/* Metrics table */}
          <div className="fld-card" data-testid="compare-metrics">
            <div className="font-head text-xl font-bold mb-2">MÉTRICAS LADO-A-LADO</div>
            <MetricRow label="Carga Aguda" v1={data.a1.metrics.acute} v2={data.a2.metrics.acute} unit="UA" />
            <MetricRow label="Carga Crónica" v1={data.a1.metrics.chronic} v2={data.a2.metrics.chronic} unit="UA" />
            <MetricRow
              label="ACWR"
              v1={data.a1.metrics.sufficient_data ? data.a1.metrics.acwr : "—"}
              v2={data.a2.metrics.sufficient_data ? data.a2.metrics.acwr : "—"}
            />
            <MetricRow label="Monotonia" v1={data.a1.metrics.monotony || "—"} v2={data.a2.metrics.monotony || "—"} />
            <MetricRow label="Strain" v1={data.a1.metrics.strain || "—"} v2={data.a2.metrics.strain || "—"} />
            <MetricRow label="Sessões" v1={data.a1.metrics.total_sessions} v2={data.a2.metrics.total_sessions} />
            <MetricRow label="Carga Média/Sessão" v1={data.a1.metrics.avg_load} v2={data.a2.metrics.avg_load} unit="UA" />
            <MetricRow label="Qualidade Sono" v1={data.a1.metrics.avg_sleep} v2={data.a2.metrics.avg_sleep} unit="/5" />
          </div>

          {/* Overlay ACWR chart */}
          <div className="fld-card" data-testid="compare-acwr-chart">
            <div className="flex items-center justify-between mb-4">
              <div className="font-head text-xl font-bold">ACWR — ÚLTIMOS 60 DIAS</div>
              <div className="text-xs hidden md:flex gap-4">
                <span className="flex items-center gap-1" style={{ color: A1_COLOR }}>
                  <span className="w-3 h-0.5 inline-block" style={{ background: A1_COLOR }} />
                  {data.a1.athlete.name}
                </span>
                <span className="flex items-center gap-1" style={{ color: A2_COLOR }}>
                  <span className="w-3 h-0.5 inline-block" style={{ background: A2_COLOR }} />
                  {data.a2.athlete.name}
                </span>
              </div>
            </div>
            {!data.a1.metrics.sufficient_data && !data.a2.metrics.sufficient_data ? (
              <div className="py-16 text-center">
                <div className="font-head text-3xl font-bold text-[#A3A3A3]">DADOS INSUFICIENTES</div>
                <p className="text-sm text-[#525252] mt-2">Ambos os atletas precisam de pelo menos 28 dias de dados.</p>
              </div>
            ) : (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.merged_series} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fill: "#525252", fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                    <YAxis domain={[0, 2]} tick={{ fill: "#A3A3A3", fontSize: 10 }} />
                    <Tooltip contentStyle={{ background: "#141414", border: "1px solid rgba(255,255,255,0.15)" }} labelStyle={{ color: "#CCFF00" }} />
                    <ReferenceArea y1={0.8} y2={1.3} fill="#00E676" fillOpacity={0.06} />
                    <Line type="monotone" dataKey="a1_acwr" stroke={A1_COLOR} strokeWidth={2.5} dot={false} name={data.a1.athlete.name} />
                    <Line type="monotone" dataKey="a2_acwr" stroke={A2_COLOR} strokeWidth={2.5} dot={false} name={data.a2.athlete.name} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
