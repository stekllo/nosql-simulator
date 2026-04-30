/** React Query hooks для админских эндпоинтов /admin/*. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  AdminUsersResponse, ChangeUserRoleResponse, UserRole,
} from "@/lib/types";


// ---------- Список пользователей ----------

export function useAdminUsers(roleFilter: UserRole | null) {
  return useQuery<AdminUsersResponse>({
    queryKey: ["admin", "users", roleFilter ?? "all"],
    queryFn: async () => {
      const qs = roleFilter ? `?role=${roleFilter}` : "";
      const { data } = await api.get<AdminUsersResponse>(`/admin/users${qs}`);
      return data;
    },
  });
}


// ---------- Смена роли ----------

interface ChangeRoleArgs {
  userId: number;
  role:   UserRole;
}

export function useChangeUserRole() {
  const qc = useQueryClient();
  return useMutation<ChangeUserRoleResponse, unknown, ChangeRoleArgs>({
    mutationFn: async ({ userId, role }) => {
      const { data } = await api.patch<ChangeUserRoleResponse>(
        `/admin/users/${userId}/role`,
        { role },
      );
      return data;
    },
    onSuccess: () => {
      // Инвалидируем список — новые роли сразу видны.
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
}
