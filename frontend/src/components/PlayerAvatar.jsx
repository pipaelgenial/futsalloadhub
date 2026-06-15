import { useState, useRef, useMemo } from "react";
import { http, formatApiError, API } from "@/lib/api";
import { toast } from "sonner";
import { User, Upload, X } from "lucide-react";

export default function PlayerAvatar({ athlete, size = 80, editable = false, onChange }) {
  const [busy, setBusy] = useState(false);
  const [v, setV] = useState(0); // cache busting
  const inputRef = useRef(null);
  const hasPhoto = !!athlete?.photo_path;
  const src = useMemo(() => {
    if (!hasPhoto) return null;
    return `${API}/athletes/${athlete.id}/photo?v=${athlete.photo_updated_at || v}`;
  }, [hasPhoto, athlete?.id, athlete?.photo_updated_at, v]);

  async function onFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp", "image/jpg"].includes(f.type)) {
      toast.error("Formato inválido. Use JPG, PNG ou WebP");
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      toast.error("Imagem demasiado grande (máx 5MB)");
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      await http.post(`/athletes/${athlete.id}/photo`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success("Foto atualizada");
      setV(Date.now());
      onChange?.();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setBusy(false); if (inputRef.current) inputRef.current.value = ""; }
  }

  async function remove() {
    if (!window.confirm("Remover foto?")) return;
    setBusy(true);
    try {
      await http.delete(`/athletes/${athlete.id}/photo`);
      toast.success("Foto removida");
      onChange?.();
    } catch (err) { toast.error(formatApiError(err)); }
    finally { setBusy(false); }
  }

  return (
    <div className="relative inline-block" style={{ width: size, height: size }} data-testid={`avatar-${athlete?.id}`}>
      <div
        className="w-full h-full overflow-hidden bg-[#1A1A1A] border border-white/10 flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        {src ? (
          <img src={src} alt={athlete?.name} className="w-full h-full object-cover" />
        ) : (
          <User className="w-1/2 h-1/2 text-[#525252]" strokeWidth={1.5} />
        )}
      </div>
      {editable && (
        <>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
            data-testid={`upload-photo-${athlete?.id}`}
            className="absolute -bottom-1 -right-1 w-7 h-7 bg-[#CCFF00] text-black flex items-center justify-center hover:bg-[#E6FF66] disabled:opacity-50"
            title="Carregar foto"
          >
            <Upload className="w-3.5 h-3.5" strokeWidth={2.5} />
          </button>
          {hasPhoto && (
            <button
              type="button"
              onClick={remove}
              disabled={busy}
              data-testid={`remove-photo-${athlete?.id}`}
              className="absolute -top-1 -right-1 w-6 h-6 bg-[#FF3B30] text-white flex items-center justify-center hover:bg-[#FF5C50] disabled:opacity-50"
              title="Remover foto"
            >
              <X className="w-3 h-3" strokeWidth={2.5} />
            </button>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={onFile}
            className="hidden"
            data-testid={`photo-input-${athlete?.id}`}
          />
        </>
      )}
    </div>
  );
}
