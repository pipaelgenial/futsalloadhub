import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const http = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Attach token from localStorage as Bearer (cross-origin cookie fallback)
http.interceptors.request.use((config) => {
  const t = localStorage.getItem("fld_token");
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export function formatApiError(err) {
  const detail = err?.response?.data?.detail;
  if (!detail) return err?.message || "Erro inesperado";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e?.msg ? e.msg : JSON.stringify(e))).join(" ");
  return String(detail);
}

/**
 * Download a file from an authenticated endpoint and trigger a browser save.
 * @param {string} path - API path (e.g. "/export/sessions.csv?start=...")
 * @param {string} fallbackName - fallback filename when server omits Content-Disposition
 */
export async function downloadFile(path, fallbackName = "download") {
  const res = await http.get(path, { responseType: "blob" });
  // Try to extract filename from Content-Disposition
  const cd = res.headers["content-disposition"] || "";
  const match = /filename="?([^"]+)"?/i.exec(cd);
  const name = match ? match[1] : fallbackName;
  const url = window.URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
