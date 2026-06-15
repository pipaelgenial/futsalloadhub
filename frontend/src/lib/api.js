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
