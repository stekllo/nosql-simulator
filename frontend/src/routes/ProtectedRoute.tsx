/** Обёртка для защищённых маршрутов — редирект на /login если нет токена. */
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuthStore } from "@/stores/auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const token    = useAuthStore((s) => s.token);
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}
