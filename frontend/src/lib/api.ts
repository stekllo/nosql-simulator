/**
 * Axios-клиент для общения с backend'ом.
 * Автоматически подставляет Bearer-токен из auth-store
 * и выкидывает пользователя на /login при 401.
 */
import axios, { AxiosError } from "axios";

import { useAuthStore } from "@/stores/auth";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: подставляем токен.
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: обрабатываем 401 глобально.
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Токен просрочен или невалиден. Сбрасываем сессию.
      useAuthStore.getState().logout();
      // Редирект на /login сделает защищённый роут.
    }
    return Promise.reject(error);
  },
);

/** Извлекает человеко-читаемое сообщение из ошибки FastAPI. */
export function extractErrorMessage(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as { detail?: string | Array<{ msg: string }> } | undefined;
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      return data.detail.map((e) => e.msg).join("; ");
    }
    return err.message;
  }
  return String(err);
}
