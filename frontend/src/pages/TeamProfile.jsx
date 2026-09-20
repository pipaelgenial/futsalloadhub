import { useEffect, useRef, useState } from "react";
import { http, formatApiError, downloadFile } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Pencil, Sliders, Download, Upload, FileDown, PenTool } from "lucide-react";
import TeamLogo from "@/components/TeamLogo";

const MAX_TEAMS = 5;

const DEFAULT_THRESHOLDS = { ideal: 300, moderate: 600, high: 900, very_high: 1200 };

// Sugestões por escalão (UA por atleta por dia)
const ESCALAO_PRESETS = {
  "Sub-13": { ideal: 200, moderate: 400, high: 600, very_high: 800 },
  "Sub-15": { ideal: 250, moderate: 500, high: 750, very_high: 1000 },
  "Sub-17": { ideal: 300, moderate: 600, high: 900, very_high: 1200 },
  "Sub-19": { ideal: 350, moderate: 700, high: 1050, very_high: 1400 },
  "Sénior": { ideal: 400, moderate: 800, high: 1200, very_high: 1600 },
};

const DEFAULT_MULTIPLIERS = { training: 1.0, match: 1.2, gym: 1.0, recovery: 0.7 };

export default function TeamProfile() {
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // id or "new"
  const [form, setForm] = useState({ name: "", escalao: "", epoca: "", coach_name: "", load_thresholds: { ...DEFAULT_THRESHOLDS }, acwr_method: "ra", session_multipliers: { ...DEFAULT_MULTIPLIERS } });
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef(null);
  const sigRef = useRef(null);

  async function exportBackup() {
    try {
      await downloadFile("/export/team-backup.zip", "backup.zip");
      toast.success("Backup gerado");
    } catch (err) { toast.error(formatApiError(err)); }
  }

  async function exportTeamFullPdf() {
    try {
      await downloadFile("/export/team/full-report.pdf", "equipa.pdf");
      toast.success("PDF da equipa gerado");
    } catch (err) { toast.error(formatApiError(err)); }
  }

  async function uploadSignature(teamId, file) {
    if (!file) return;
    try {
      const fd = new FormData();
      fd.append("file", file);
      await http.post(`/teams/${teamId}/signature`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Assinatura guardada");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  }

  async function removeSignature(teamId) {
    if (!window.confirm("Remover a assinatura da equipa?")) return;
    try {
      await http.delete(`/teams/${teamId}/signature`);
      toast.success("Assinatura removida");
      load();
    } catch (err) { toast.error(formatApiError(err)); }
  }

  async function importBackup(e) {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    const mode = window.confirm(
      "Como queres importar?\n\nOK = SUBSTITUIR (apaga atletas e sessões atuais)\nCancelar = ADICIONAR (mantém dados atuais, só adiciona novos)"
    ) ? "replace" : "merge";
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const { data } = await http.post(`/import/team-backup?mode=${mode}`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(
        `Import concluído · ${data.athletes_created} atletas novos, ${data.athletes_matched} correspondidos, ${data.sessions_created} sessões, ${data.sessions_skipped} ignoradas`
      );
      window.dispatchEvent(new Event("active-team-changed"));
    } catch (err) { toast.error(formatApiError(err)); }
    finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function load() {
    setLoading(true);
    try {
      const { data } = await http.get("/teams");
      setTeams(data);
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  function startNew() {
    if (teams.length >= MAX_TEAMS) {
      toast.error(`Limite de ${MAX_TEAMS} equipas atingido`);
      return;
    }
    setEditing("new");
    setForm({ name: "", escalao: "", epoca: "", coach_name: "", load_thresholds: { ...DEFAULT_THRESHOLDS }, acwr_method: "ra", session_multipliers: { ...DEFAULT_MULTIPLIERS } });
  }

  function startEdit(t) {
    setEditing(t.id);
    setForm({
      name: t.name,
      escalao: t.escalao,
      epoca: t.epoca,
      coach_name: t.coach_name || "",
      load_thresholds: t.load_thresholds || { ...DEFAULT_THRESHOLDS },
      acwr_method: t.acwr_method || "ra",
      session_multipliers: { ...DEFAULT_MULTIPLIERS, ...(t.session_multipliers || {}) },
    });
  }

  function cancel() {
    setEditing(null);
    setForm({ name: "", escalao: "", epoca: "", coach_name: "", load_thresholds: { ...DEFAULT_THRESHOLDS }, acwr_method: "ra", session_multipliers: { ...DEFAULT_MULTIPLIERS } });
  }

  function setThreshold(key, value) {
    setForm((f) => ({ ...f, load_thresholds: { ...f.load_thresholds, [key]: value } }));
  }

  function applyPreset(presetName) {
    const p = ESCALAO_PRESETS[presetName];
    if (!p) return;
    setForm((f) => ({ ...f, load_thresholds: { ...p } }));
    toast.success(`Predefinição ${presetName} aplicada`);
  }

  function resetThresholdsDefault() {
    setForm((f) => ({ ...f, load_thresholds: { ...DEFAULT_THRESHOLDS } }));
    toast.info("Limiares repostos para os predefinidos");
  }

  function validateThresholds(t) {
    const v = [t.ideal, t.moderate, t.high, t.very_high].map(Number);
    if (v.some((x) => !Number.isFinite(x) || x <= 0)) return "Todos os limiares devem ser positivos.";
    if (!(v[0] < v[1] && v[1] < v[2] && v[2] < v[3])) return "Os limiares devem ser crescentes (ideal < moderada < alta < muito alta).";
    return null;
  }

  async function save(e) {
    e.preventDefault();
    const validationErr = validateThresholds(form.load_thresholds);
    if (validationErr) { toast.error(validationErr); return; }
    setSaving(true);
    try {
      const payload = {
        name: form.name,
        escalao: form.escalao,
        epoca: form.epoca,
        coach_name: form.coach_name || null,
        acwr_method: form.acwr_method || "ra",
        session_multipliers: {
          training: Number(form.session_multipliers.training) || 1.0,
          match: Number(form.session_multipliers.match) || 1.2,
          gym: Number(form.session_multipliers.gym) || 1.0,
          recovery: Number(form.session_multipliers.recovery) || 0.7,
        },
        load_thresholds: {
          ideal: Number(form.load_thresholds.ideal),
          moderate: Number(form.load_thresholds.moderate),
          high: Number(form.load_thresholds.high),
          very_high: Number(form.load_thresholds.very_high),
        },
      };
      if (editing === "new") {
        await http.post("/teams", payload);
        toast.success("Equipa criada");
      } else {
        await http.put(`/teams/${editing}`, payload);
        toast.success("Equipa atualizada");
      }
      cancel();
      load();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setSaving(false); }
  }

  async function remove(t) {
    const txt = window.prompt(`Eliminar a equipa "${t.name}" e TODOS os seus dados (atletas, sessões, lesões)?\n\nEscreva ELIMINAR (em maiúsculas) para confirmar:`);
    if (txt !== "ELIMINAR") return;
    try {
      await http.delete(`/teams/${t.id}`);
      toast.success("Equipa eliminada");
      load();
      window.dispatchEvent(new Event("active-team-changed"));
    } catch (err) { toast.error(formatApiError(err)); }
  }

  if (loading) return <div className="text-[#A3A3A3]">A carregar...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <div className="text-xs text-[#CCFF00] tracking-[0.3em] uppercase mb-2">Perfil</div>
          <h1 className="font-head text-3xl sm:text-4xl md:text-5xl font-black leading-none">EQUIPAS</h1>
          <p className="text-[#A3A3A3] text-sm mt-2">Até {MAX_TEAMS} equipas com dados independentes</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={exportTeamFullPdf}
            disabled={teams.length === 0}
            className="fld-btn-ghost flex items-center gap-2 disabled:opacity-40"
            data-testid="export-team-pdf-btn"
            title="Descarregar um PDF com o registo completo de todos os atletas da equipa ativa"
          >
            <FileDown className="w-4 h-4" /> PDF DA EQUIPA
          </button>
          <button
            onClick={exportBackup}
            disabled={teams.length === 0}
            className="fld-btn-ghost flex items-center gap-2 disabled:opacity-40"
            data-testid="export-backup-btn"
            title="Descarregar um ZIP com atletas.csv + sessoes.csv da equipa ativa"
          >
            <Download className="w-4 h-4" /> EXPORTAR BACKUP
          </button>
          <label
            className={`fld-btn-ghost flex items-center gap-2 cursor-pointer ${importing || teams.length === 0 ? "opacity-40 pointer-events-none" : ""}`}
            data-testid="import-backup-label"
            title="Importar um backup ZIP (atletas.csv + sessoes.csv) para a equipa ativa"
          >
            <Upload className="w-4 h-4" /> {importing ? "A IMPORTAR..." : "IMPORTAR BACKUP"}
            <input
              ref={fileRef}
              type="file"
              accept=".zip,.csv"
              onChange={importBackup}
              disabled={importing || teams.length === 0}
              className="hidden"
              data-testid="import-backup-input"
            />
          </label>
          <button
            onClick={startNew}
            disabled={teams.length >= MAX_TEAMS || editing !== null}
            className="fld-btn-primary flex items-center gap-2 disabled:opacity-50"
            data-testid="add-team-btn"
          >
            <Plus className="w-4 h-4" /> NOVA EQUIPA <span className="text-xs">({teams.length}/{MAX_TEAMS})</span>
          </button>
        </div>
      </div>

      {teams.length === 0 && editing !== "new" && (
        <div className="fld-card border-l-4 border-l-[#CCFF00]" data-testid="empty-team-msg">
          <div className="font-head text-xl sm:text-2xl font-bold">INSIRA DADOS DA EQUIPA</div>
          <p className="text-[#A3A3A3] text-sm mt-2">Crie a sua primeira equipa para começar.</p>
        </div>
      )}

      {editing && (
        <form onSubmit={save} className="fld-card max-w-2xl space-y-5" data-testid="team-form">
          <div className="font-head text-lg">{editing === "new" ? "NOVA EQUIPA" : "EDITAR EQUIPA"}</div>
          <div>
            <label className="fld-label">Nome da Equipa</label>
            <input className="fld-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required data-testid="team-name" placeholder="Ex: Sporting Futsal" />
          </div>
          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <label className="fld-label">Escalão</label>
              <input className="fld-input" value={form.escalao} onChange={(e) => setForm({ ...form, escalao: e.target.value })} required data-testid="team-escalao" placeholder="Ex: Sénior, Sub-19" />
            </div>
            <div>
              <label className="fld-label">Época</label>
              <input className="fld-input" value={form.epoca} onChange={(e) => setForm({ ...form, epoca: e.target.value })} required data-testid="team-epoca" placeholder="Ex: 2025/2026" />
            </div>
          </div>
          <div>
            <label className="fld-label">Nome do Treinador (para assinatura nos PDFs)</label>
            <input
              className="fld-input"
              value={form.coach_name}
              onChange={(e) => setForm({ ...form, coach_name: e.target.value })}
              data-testid="team-coach-name"
              placeholder="Ex: Pedro Pipa"
            />
          </div>

          {/* ACWR calculation method */}
          <div className="border-t border-white/5 pt-5">
            <div className="font-head text-sm uppercase tracking-widest mb-1">Método de Cálculo do ACWR</div>
            <p className="text-[10px] text-[#525252] mb-3">
              <b>RA</b> — Rolling Average 1:4 (soma 7d / média de 4×7d). Método clássico de Gabbett.<br />
              <b>EWMA</b> — Exponentially Weighted Moving Average (Williams et al. 2016). Dá mais peso aos dias recentes; menos sensível a falsos alarmes.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setForm((f) => ({ ...f, acwr_method: "ra" }))}
                data-testid="acwr-method-ra"
                className={`py-3 px-4 border text-left transition-all ${
                  form.acwr_method === "ra"
                    ? "border-[#CCFF00] bg-[#CCFF00]/10 text-[#CCFF00]"
                    : "border-white/10 hover:border-white/30 text-[#A3A3A3]"
                }`}
              >
                <div className="font-head text-xs uppercase tracking-widest">Rolling Average</div>
                <div className="text-[10px] mt-1 opacity-70">1:4 · Soma 7d / Média 4×7d</div>
              </button>
              <button
                type="button"
                onClick={() => setForm((f) => ({ ...f, acwr_method: "ewma" }))}
                data-testid="acwr-method-ewma"
                className={`py-3 px-4 border text-left transition-all ${
                  form.acwr_method === "ewma"
                    ? "border-[#CCFF00] bg-[#CCFF00]/10 text-[#CCFF00]"
                    : "border-white/10 hover:border-white/30 text-[#A3A3A3]"
                }`}
              >
                <div className="font-head text-xs uppercase tracking-widest">EWMA</div>
                <div className="text-[10px] mt-1 opacity-70">λ=0.25 / λ=0.069 · pesos exp. decrescentes</div>
              </button>
            </div>
          </div>

          {/* Session-type multipliers (applied in EWMA & adjusted load) */}
          <div className="border-t border-white/5 pt-5" data-testid="session-multipliers-block">
            <div className="font-head text-sm uppercase tracking-widest mb-1">Multiplicadores por Tipo de Sessão</div>
            <p className="text-[10px] text-[#525252] mb-3">
              Ajusta o peso relativo de cada sessão na "carga ajustada" (usada no EWMA).
              Valor entre 0.1 e 3.0. Ex.: jogo &gt; treino &gt; ginásio &gt; recuperação.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { key: "training", label: "Treino", color: "#CCFF00" },
                { key: "match", label: "Jogo", color: "#FF3B30" },
                { key: "gym", label: "Ginásio", color: "#FFEA00" },
                { key: "recovery", label: "Recuperação", color: "#00B0FF" },
              ].map((row) => (
                <div key={row.key}>
                  <label className="fld-label flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full inline-block" style={{ background: row.color }} />
                    {row.label}
                  </label>
                  <input
                    className="fld-input"
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="3"
                    value={form.session_multipliers[row.key]}
                    onChange={(e) => setForm((f) => ({
                      ...f,
                      session_multipliers: { ...f.session_multipliers, [row.key]: e.target.value },
                    }))}
                    data-testid={`mult-${row.key}`}
                    required
                  />
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setForm((f) => ({ ...f, session_multipliers: { ...DEFAULT_MULTIPLIERS } }))}
              className="text-[10px] uppercase tracking-widest text-[#A3A3A3] hover:text-[#CCFF00] mt-2"
              data-testid="mult-reset"
            >
              Repor predefinidos (1.0 / 1.2 / 1.0 / 0.7)
            </button>
          </div>

          {/* Limiares de carga por atleta */}
          <div className="border-t border-white/5 pt-5">
            <div className="flex items-start gap-2 mb-3">
              <Sliders className="w-4 h-4 text-[#CCFF00] mt-0.5" />
              <div className="flex-1">
                <div className="font-head text-sm uppercase tracking-widest">Limiares de Carga por Atleta (UA/dia)</div>
                <p className="text-[10px] text-[#525252] mt-1">
                  Controlam as cores no calendário. Ajuste conforme o escalão — um Sub-15 não tem a mesma capacidade que um Sénior.
                </p>
              </div>
            </div>

            {/* Presets per escalão */}
            <div className="flex flex-wrap gap-1.5 mb-3" data-testid="threshold-presets">
              <span className="text-[10px] uppercase tracking-widest text-[#525252] self-center mr-1">Predefinições:</span>
              {Object.keys(ESCALAO_PRESETS).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => applyPreset(p)}
                  data-testid={`threshold-preset-${p}`}
                  className="text-[10px] uppercase tracking-widest px-2 py-1 border border-white/10 hover:border-[#CCFF00]/60 hover:text-[#CCFF00] transition-all"
                >
                  {p}
                </button>
              ))}
              <button
                type="button"
                onClick={resetThresholdsDefault}
                data-testid="threshold-reset"
                className="text-[10px] uppercase tracking-widest px-2 py-1 border border-white/10 text-[#A3A3A3] hover:text-white transition-all ml-auto"
              >
                Repor 300/600/900/1200
              </button>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div>
                <label className="fld-label flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#CCFF00]" /> Ideal &lt;</label>
                <input
                  className="fld-input"
                  type="number"
                  min="1"
                  value={form.load_thresholds.ideal}
                  onChange={(e) => setThreshold("ideal", e.target.value)}
                  data-testid="threshold-ideal"
                  required
                />
              </div>
              <div>
                <label className="fld-label flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#FFEA00]" /> Moderada &lt;</label>
                <input
                  className="fld-input"
                  type="number"
                  min="1"
                  value={form.load_thresholds.moderate}
                  onChange={(e) => setThreshold("moderate", e.target.value)}
                  data-testid="threshold-moderate"
                  required
                />
              </div>
              <div>
                <label className="fld-label flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#FF9500]" /> Alta &lt;</label>
                <input
                  className="fld-input"
                  type="number"
                  min="1"
                  value={form.load_thresholds.high}
                  onChange={(e) => setThreshold("high", e.target.value)}
                  data-testid="threshold-high"
                  required
                />
              </div>
              <div>
                <label className="fld-label flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#FF3B30]" /> Muito alta &lt;</label>
                <input
                  className="fld-input"
                  type="number"
                  min="1"
                  value={form.load_thresholds.very_high}
                  onChange={(e) => setThreshold("very_high", e.target.value)}
                  data-testid="threshold-very-high"
                  required
                />
              </div>
            </div>
            <p className="text-[10px] text-[#525252] mt-2">
              Cinza &lt; {form.load_thresholds.ideal || "—"} · Lime &lt; {form.load_thresholds.moderate || "—"} · Amarelo &lt; {form.load_thresholds.high || "—"} · Laranja &lt; {form.load_thresholds.very_high || "—"} · Vermelho ≥ {form.load_thresholds.very_high || "—"}
            </p>
          </div>
          <div className="flex gap-3">
            <button type="submit" className="fld-btn-primary" disabled={saving} data-testid="team-save">
              {saving ? "A GUARDAR..." : "GUARDAR"}
            </button>
            <button type="button" className="fld-btn-ghost" onClick={cancel} data-testid="team-cancel">CANCELAR</button>
          </div>
        </form>
      )}

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teams.map((t) => (
          <div
            key={t.id}
            className={`fld-card relative ${t.active ? "border-l-4 border-l-[#CCFF00]" : ""}`}
            data-testid={`team-card-${t.id}`}
          >
            <div className="flex items-start gap-3 mb-3">
              <TeamLogo team={t} size={56} editable onChange={load} />
              <div className="flex-1 min-w-0">
                <div className="font-head text-lg font-bold truncate">{t.name}</div>
                <div className="text-xs text-[#A3A3A3] uppercase tracking-widest">{t.escalao}</div>
                <div className="text-xs text-[#525252] mt-0.5">{t.epoca}</div>
                {t.coach_name && (
                  <div className="text-[10px] text-[#A3A3A3] mt-0.5 truncate" title="Treinador (aparece na assinatura dos PDFs)">
                    Treinador: <span className="text-white">{t.coach_name}</span>
                  </div>
                )}
                <div className="mt-1.5 inline-block text-[9px] font-head font-extrabold uppercase tracking-widest px-1.5 py-0.5 border border-white/10 text-[#A3A3A3]" title="Método de cálculo do ACWR">
                  ACWR: {(t.acwr_method || "ra").toUpperCase()}
                </div>
              </div>
              {t.active && (
                <span className="text-[10px] uppercase tracking-widest text-[#CCFF00] border border-[#CCFF00]/40 bg-[#CCFF00]/10 px-2 py-0.5" data-testid={`team-active-${t.id}`}>
                  Ativa
                </span>
              )}
            </div>

            {/* Signature */}
            <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-3">
              {t.signature_updated_at ? (
                <img
                  src={`${process.env.REACT_APP_BACKEND_URL}/api/teams/${t.id}/signature?v=${encodeURIComponent(t.signature_updated_at)}`}
                  alt="Assinatura"
                  className="h-8 max-w-[100px] object-contain bg-white/5 px-2 py-1 border border-white/10"
                  data-testid={`team-signature-preview-${t.id}`}
                />
              ) : (
                <div className="h-8 w-[100px] border border-dashed border-white/10 text-[9px] text-[#525252] uppercase tracking-widest flex items-center justify-center">
                  Sem assinatura
                </div>
              )}
              <label
                className="fld-btn-ghost text-xs flex items-center gap-1 cursor-pointer"
                data-testid={`upload-signature-${t.id}`}
                title="Upload de assinatura (PNG transparente recomendado)"
              >
                <PenTool className="w-3.5 h-3.5" />
                {t.signature_updated_at ? "Substituir" : "Assinatura"}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                  onChange={(e) => uploadSignature(t.id, e.target.files && e.target.files[0])}
                />
              </label>
              {t.signature_updated_at && (
                <button
                  type="button"
                  onClick={() => removeSignature(t.id)}
                  className="fld-btn-ghost text-xs text-[#FF3B30] border-[#FF3B30]/30 hover:bg-[#FF3B30]/10 flex items-center"
                  data-testid={`remove-signature-${t.id}`}
                  title="Remover a assinatura"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/5">
              <button onClick={() => startEdit(t)} className="fld-btn-ghost text-xs flex items-center gap-1 flex-1" data-testid={`edit-team-${t.id}`}>
                <Pencil className="w-3.5 h-3.5" /> EDITAR
              </button>
              <button onClick={() => remove(t)} className="fld-btn-ghost text-xs flex items-center gap-1 text-[#FF3B30] border-[#FF3B30]/30 hover:bg-[#FF3B30]/10" data-testid={`delete-team-${t.id}`}>
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
