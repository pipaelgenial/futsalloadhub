import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { http, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { RiskBadge, MetricCard, zoneColor, SESSION_TYPES, SESSION_TYPE_ORDER, SessionTypeBadge } from "@/components/Bits";
import InjuriesPanel from "@/components/InjuriesPanel";
import PlayerAvatar from "@/components/PlayerAvatar";
import { ArrowLeft, Trash2, ShieldAlert, Pencil, X, Check } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceArea, CartesianGrid,
} from "recharts";

export default function AthleteDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [injuries, setInjuries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // session id being edited
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [{ data }, { data: inj }] = await Promise.all([
        http.get(`/analytics/athlete/${id}`),
        http.get(`/injuries?athlete_id=${id}`),
      ]);
      setData(data);
      setInjuries(inj);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [id]);

  function startEdit(s) {
    setEditing(s.id);
    setEditForm({
      date: s.date,
      rpe: s.rpe,
      duration_min: s.duration_min,
      sleep_quality: s.sleep_quality,
      wellness: s.wellness ?? 7,
      session_type: s.session_type || "training",
      notes: s.notes || "",
    });
  }

  function cancelEdit() { setEditing(null); setEditForm({}); }

  async function saveEdit(sid) {
    setSaving(true);
    try {
      await http.put(`/sessions/${sid}`, {
        date: editForm.date,
        rpe: Number(editForm.rpe),
        duration_min: Number(editForm.duration_min),
        sleep_quality: Number(editForm.sleep_quality),
        wellness: Number(editForm.wellness),
        session_type: editForm.session_type,
        notes: editForm.notes || null,
      });
      toast.success("Sessão atualizada");
      setEditing(null);
      setEditForm({});
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  async function delSession(sid) {
    if (!window.confirm("Eliminar sessão?")) return;
    try {
      await http.delete(`/sessions/${sid}`);
      toast.success("Eliminada");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  }

  if (loading) return <div className="text-[#A3A3A3]">A carregar...</div>;
  if (!data) return <div className="text-[#A3A3A3]">Sem dados.</div>;

  const { athlete, metrics, series, sessions } = data;

  return (
    <div className="space-y-8">
      <Link to="/atletas" className="inline-flex items-center gap-2 text-xs text-[#A3A3A3] uppercase tracking-widest hover:text-[#CCFF00]">
        <ArrowLeft className="w-3.5 h-3.5" /> Voltar
      </Link>

      <div className="flex items-start justify-between flex-wrap gap-6">
        <div className="flex items-center gap-5">
          <PlayerAvatar athlete={athlete} size={96} editable onChange={load} />
          <div>
            <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Perfil de Atleta</div>
            <h1 className="font-head text-4xl md:text-5xl font-black leading-none">{athlete.name}</h1>
            <div className="mt-2 text-[#A3A3A3] text-sm">
              {athlete.jersey_number && <span className="text-[#CCFF00] metric-num mr-2">#{athlete.jersey_number}</span>}
              {athlete.position}
            </div>
          </div>
        </div>
        <div className="text-right">
          <RiskBadge risk={metrics.risk} testid="athlete-risk-badge" />
          {metrics.risk_description && (
            <div className="text-xs text-[#A3A3A3] max-w-md mt-2" data-testid="athlete-risk-description">
              {metrics.risk_description}
            </div>
          )}
        </div>
      </div>

      {/* Context alert: link risk + injuries */}
      {(() => {
        const active = injuries.filter((i) => !i.end_date);
        const recent = injuries.filter((i) => {
          if (!i.end_date) return false;
          const end = new Date(i.end_date);
          const diff = (Date.now() - end.getTime()) / (1000 * 60 * 60 * 24);
          return diff <= 120;
        });
        if (active.length === 0 && recent.length === 0) return null;
        const isRisk = metrics.risk === "danger" || metrics.risk === "warning";
        return (
          <div
            className="fld-card flex items-start gap-4"
            style={{ borderLeft: `4px solid ${isRisk ? "#FF3B30" : "#FFEA00"}` }}
            data-testid="injury-context-alert"
          >
            <ShieldAlert className="w-6 h-6 mt-0.5" style={{ color: isRisk ? "#FF3B30" : "#FFEA00" }} />
            <div>
              <div className="font-head text-lg font-bold mb-1">
                {isRisk ? "ALERTA CONTEXTUALIZADO" : "HISTÓRICO RECENTE"}
              </div>
              <div className="text-sm text-[#A3A3A3]">
                {active.length > 0 && (
                  <>Atleta com lesão <span className="text-white font-semibold">ativa</span>: {active.map((i) => `${i.type} (${i.body_part})`).join(", ")}.{" "}</>
                )}
                {recent.length > 0 && active.length === 0 && (
                  <>Lesão recente nos últimos 4 meses: {recent.map((i) => `${i.type} (${i.body_part})`).join(", ")}.{" "}</>
                )}
                {isRisk && " O ACWR atual exige cautela adicional dado o histórico."}
              </div>
            </div>
          </div>
        );
      })()}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <MetricCard label="Carga Aguda" value={metrics.acute} unit="UA" testid="metric-acute" />
        <MetricCard label="Carga Crónica" value={metrics.chronic} unit="UA" testid="metric-chronic" />
        <MetricCard label="ACWR" value={metrics.sufficient_data ? metrics.acwr : "—"} accent testid="metric-acwr" zoneCol={metrics.sufficient_data ? zoneColor(metrics.acwr_zone) : null} />
        <MetricCard label="Monotonia" value={metrics.monotony || "—"} testid="metric-monotony" zoneCol={metrics.monotony ? zoneColor(metrics.monotony_zone) : null} />
        <MetricCard label="Strain" value={metrics.strain || "—"} testid="metric-strain" zoneCol={metrics.strain ? zoneColor(metrics.strain_zone) : null} />
        <MetricCard
          label="Bem-Estar (7d)"
          value={metrics.wellness_7d || "—"}
          unit={metrics.wellness_7d ? "/10" : null}
          testid="metric-wellness"
          zoneCol={metrics.wellness_7d ? (
            metrics.wellness_zone === "depleted" ? "#FF3B30"
            : metrics.wellness_zone === "fatigued" ? "#FF9500"
            : metrics.wellness_zone === "moderate" ? "#FFEA00"
            : metrics.wellness_zone === "good" ? "#00E676"
            : "#CCFF00"
          ) : null}
        />
      </div>

      <div className="fld-card">
        <div className="flex items-center justify-between mb-4">
          <div className="font-head text-2xl font-bold">EVOLUÇÃO ACWR (60 DIAS)</div>
          <div className="text-xs text-[#A3A3A3] hidden md:flex gap-4">
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#CCFF00] inline-block" /> ACWR</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-white inline-block" /> Aguda</span>
            <span className="flex items-center gap-1"><span className="w-3 h-0.5 bg-[#A3A3A3] inline-block" /> Crónica</span>
          </div>
        </div>
        {!metrics.sufficient_data ? (
          <div className="py-16 text-center" data-testid="insufficient-detail">
            <div className="font-head text-3xl font-bold text-[#A3A3A3] mb-2">DADOS INSUFICIENTES</div>
            <p className="text-sm text-[#525252]">
              {metrics.days_since_first === 0
                ? "Sem sessões registadas ainda."
                : `Faltam ${Math.max(0, 28 - metrics.days_since_first)} dias para o ACWR estar disponível.`}
            </p>
          </div>
        ) : (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fill: "#525252", fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis yAxisId="left" tick={{ fill: "#525252", fontSize: 10 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: "#CCFF00", fontSize: 10 }} domain={[0, 2]} />
                <Tooltip contentStyle={{ background: "#141414", border: "1px solid rgba(255,255,255,0.15)" }} labelStyle={{ color: "#CCFF00" }} />
                <ReferenceArea yAxisId="right" y1={0.8} y2={1.3} fill="#00E676" fillOpacity={0.06} />
                <Line yAxisId="left" type="monotone" dataKey="acute" stroke="#FFFFFF" strokeWidth={1.5} dot={false} />
                <Line yAxisId="left" type="monotone" dataKey="chronic" stroke="#A3A3A3" strokeWidth={1.5} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="acwr" stroke="#CCFF00" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <InjuriesPanel athleteId={id} refreshKey={injuries.length} onChange={load} />

      <div className="fld-card">
        <div className="font-head text-2xl font-bold mb-4">SESSÕES ({sessions.length})</div>
        {sessions.length === 0 ? (
          <div className="text-sm text-[#A3A3A3]">Nenhuma sessão registada.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-widest text-[#525252] border-b border-white/5">
                  <th className="py-3 pr-4">Data</th>
                  <th className="py-3 px-2">Tipo</th>
                  <th className="py-3 px-2">RPE</th>
                  <th className="py-3 px-2">Duração</th>
                  <th className="py-3 px-2">Sono</th>
                  <th className="py-3 px-2">Bem-Estar</th>
                  <th className="py-3 px-2 text-[#CCFF00]">Carga</th>
                  <th className="py-3 px-2 text-right">Ações</th>
                </tr>
              </thead>
              <tbody>
                {sessions.slice(0, 30).map((s) => {
                  const isEditing = editing === s.id;
                  const wellness = s.wellness ?? "—";
                  if (isEditing) {
                    const computed = (Number(editForm.rpe) || 0) * (Number(editForm.duration_min) || 0);
                    return (
                      <tr key={s.id} className="border-b border-white/5 bg-white/[0.02]" data-testid={`edit-row-${s.id}`}>
                        <td className="py-2 pr-4">
                          <input type="date" className="fld-input py-1 px-2 text-sm" value={editForm.date} onChange={(e) => setEditForm({ ...editForm, date: e.target.value })} data-testid={`edit-date-${s.id}`} />
                        </td>
                        <td className="py-2 px-2">
                          <select className="fld-input py-1 px-2 text-sm" value={editForm.session_type} onChange={(e) => setEditForm({ ...editForm, session_type: e.target.value })} data-testid={`edit-type-${s.id}`}>
                            {SESSION_TYPE_ORDER.map((k) => (
                              <option key={k} value={k}>{SESSION_TYPES[k].label}</option>
                            ))}
                          </select>
                        </td>
                        <td className="py-2 px-2">
                          <input type="number" min="1" max="10" className="fld-input py-1 px-2 w-16 text-sm metric-num" value={editForm.rpe} onChange={(e) => setEditForm({ ...editForm, rpe: e.target.value })} data-testid={`edit-rpe-${s.id}`} />
                        </td>
                        <td className="py-2 px-2">
                          <input type="number" min="1" max="300" className="fld-input py-1 px-2 w-20 text-sm" value={editForm.duration_min} onChange={(e) => setEditForm({ ...editForm, duration_min: e.target.value })} data-testid={`edit-duration-${s.id}`} />
                        </td>
                        <td className="py-2 px-2">
                          <input type="number" min="1" max="5" className="fld-input py-1 px-2 w-14 text-sm" value={editForm.sleep_quality} onChange={(e) => setEditForm({ ...editForm, sleep_quality: e.target.value })} data-testid={`edit-sleep-${s.id}`} />
                        </td>
                        <td className="py-2 px-2">
                          <input type="number" min="1" max="10" className="fld-input py-1 px-2 w-14 text-sm" value={editForm.wellness} onChange={(e) => setEditForm({ ...editForm, wellness: e.target.value })} data-testid={`edit-wellness-${s.id}`} />
                        </td>
                        <td className="py-2 px-2 metric-num text-[#CCFF00]">{computed}</td>
                        <td className="py-2 px-2">
                          <div className="flex justify-end gap-2">
                            <button onClick={() => saveEdit(s.id)} disabled={saving} className="text-[#CCFF00] hover:text-white" data-testid={`save-session-${s.id}`} title="Guardar">
                              <Check className="w-4 h-4" />
                            </button>
                            <button onClick={cancelEdit} className="text-[#525252] hover:text-white" data-testid={`cancel-session-${s.id}`} title="Cancelar">
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  }
                  return (
                    <tr key={s.id} className="border-b border-white/5" data-testid={`session-row-${s.id}`}>
                      <td className="py-2 pr-4">{s.date}</td>
                      <td className="py-2 px-2"><SessionTypeBadge type={s.session_type || "training"} size="sm" /></td>
                      <td className="py-2 px-2 metric-num">{s.rpe}</td>
                      <td className="py-2 px-2">{s.duration_min}min</td>
                      <td className="py-2 px-2">{s.sleep_quality}/5</td>
                      <td className="py-2 px-2 metric-num">{wellness}<span className="text-[#525252] text-xs">/10</span></td>
                      <td className="py-2 px-2 metric-num text-[#CCFF00]">{s.load}</td>
                      <td className="py-2 px-2">
                        <div className="flex justify-end gap-2">
                          <button onClick={() => startEdit(s)} className="text-[#525252] hover:text-[#CCFF00]" data-testid={`edit-session-${s.id}`} title="Editar">
                            <Pencil className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => delSession(s.id)} className="text-[#525252] hover:text-[#FF3B30]" data-testid={`delete-session-${s.id}`} title="Eliminar">
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
