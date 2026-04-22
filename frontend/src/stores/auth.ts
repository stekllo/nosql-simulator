/**
 * Store авторизации.
 * Держит токен + профиль пользователя, сохраняет в localStorage
 * чтобы перезагрузка страницы не выкидывала из сессии.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { User } from "@/lib/types";

interface AuthState {
  token: string | null;
  user:  User   | null;

  setAuth: (token: string, user: User) => void;
  setUser: (user: User)                => void;
  logout:  ()                           => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user:  null,

      setAuth: (token, user) => set({ token, user }),
      setUser: (user)        => set({ user }),
      logout:  ()            => set({ token: null, user: null }),
    }),
    {
      name: "nosql-sim-auth",
      // Сохраняем только токен. Профиль можно перезапросить по токену.
      partialize: (state) => ({ token: state.token }),
    },
  ),
);
