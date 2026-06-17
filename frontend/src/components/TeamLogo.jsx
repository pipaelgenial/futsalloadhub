import { useState, useRef, useMemo } from "react";
import { http, formatApiError, API } from "@/lib/api";
import { toast } from "sonner";
import { Shield, Upload, X } from "lucide-react";

export default function TeamLogo({ team, size = 64, editable = false, onChange }) {
  const [busy, setBusy] = useState(false);
  const [v, setV] = useState(0);
  const inputRef = useRef(null);
  const hasLogo = !!team?.logo_path;
  const src = useMemo(() => {
    if (!hasLogo) return null;
    return `${API}/teams/${team.id}/logo?v=${team.logo_updated_at || v}`;
  }, [hasLogo, team?.id, team?.logo_updated_at, v]);

  async function onFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp", "image/jpg"].includes(f.type)) {
      toast.error("Formato inválido. Use JPG, PNG ou WebP");
      return;
    }
    if (f.size > 5 * 1024 * 1024) { toast.error("Imagem demasiado grande (máx 5MB)"); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      await http.post(`/teams/${team.id}/logo`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success("Logo atualizado");
      setV(Date.now());
      onChange?.();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function remove() {
    if (!window.confirm("Remover logo?")) return;
    setBusy(true);
    try {
      await http.delete(`/teams/${team.id}/logo`);
      toast.success("Logo removido");
      onChange?.();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setBusy(false); }
  }

  return (
    <div className="relative inline-block" style={{ width: size, height: size }} data-testid={`team-logo-${team?.id}`}>
      <div
        className="w-full h-full overflow-hidden bg-[#1A1A1A] border border-white/10 flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        {src ? (
          <img src={src} alt={team?.name} className="w-full h-full object-contain" />
        ) : (
          <Shield className="w-1/2 h-1/2 text-[#525252]" strokeWidth={1.5} />
        )}
      </div>
      {editable && (
        <>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
            data-testid={`upload-team-logo-${team?.id}`}
            className="absolute -bottom-1 -right-1 w-6 h-6 bg-[#CCFF00] text-black flex items-center justify-center hover:bg-[#E6FF66] disabled:opacity-50"
            title="Carregar logo"
          >
            <Upload className="w-3 h-3" strokeWidth={2.5} />
          </button>
          {hasLogo && (
            <button
              type="button"
              onClick={remove}
              disabled={busy}
              data-testid={`remove-team-logo-${team?.id}`}
              className="absolute -top-1 -right-1 w-5 h-5 bg-[#FF3B30] text-white flex items-center justify-center hover:bg-[#FF5C50] disabled:opacity-50"
              title="Remover logo"
            >
              <X className="w-2.5 h-2.5" strokeWidth={2.5} />
            </button>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={onFile}
            className="hidden"
          />
        </>
      )}
    </div>
  );
}
