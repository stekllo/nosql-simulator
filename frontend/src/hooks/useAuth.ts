/**
 * React Query hooks для эндпоинтов /auth.
 * Вся работа с API идёт через эти обёртки — компоненты получают
 * стандартные объекты { data, isPending, error } без ручного useState.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import type { LoginResponse, RegisterRequest, User } from "@/lib/types";


// ---------- /auth/me ----------

export function useMe() {
  const token = useAuthStore((s) => s.token);

  return useQuery<User>({
    queryKey: ["auth", "me"],
    queryFn: async () => {
      const { data } = await api.get<User>("/auth/me");
      // При каждом успешном ответе обновляем профиль в сторе.
      useAuthStore.getState().setUser(data);
      return data;
    },
    enabled:   !!token,        // не запрашивать, если нет токена
    staleTime: 5 * 60_000,     // 5 минут свежести
    retry:     false,
  });
}


// ---------- /auth/login ----------

interface LoginArgs { username: string; password: string }

export function useLogin() {
  const qc = useQueryClient();

  return useMutation<LoginResponse, unknown, LoginArgs>({
    mutationFn: async ({ username, password }) => {
      // FastAPI OAuth2PasswordRequestForm ожидает form-urlencoded.
      const body = new URLSearchParams();
      body.set("username", username);
      body.set("password", password);

      const { data } = await api.post<LoginResponse>("/auth/login", body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      return data;
    },
    onSuccess: async (res) => {
      // 1. Кладём токен в store — api-клиент его сразу подхватит.
      useAuthStore.getState().setAuth(res.access_token, {} as User);
      // 2. Вытягиваем профиль по новому токену.
      const { data: me } = await api.get<User>("/auth/me");
      useAuthStore.getState().setAuth(res.access_token, me);
      qc.setQueryData(["auth", "me"], me);
    },
  });
}


// ---------- /auth/register ----------

export function useRegister() {
  const qc = useQueryClient();

  return useMutation<LoginResponse, unknown, RegisterRequest>({
    mutationFn: async (body) => {
      const { data } = await api.post<LoginResponse>("/auth/register", body);
      return data;
    },
    onSuccess: async (res) => {
      useAuthStore.getState().setAuth(res.access_token, {} as User);
      const { data: me } = await api.get<User>("/auth/me");
      useAuthStore.getState().setAuth(res.access_token, me);
      qc.setQueryData(["auth", "me"], me);
    },
  });
}
