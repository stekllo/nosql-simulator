/** Hooks для эндпоинтов /me — dashboard и история. */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { DashboardResponse, SubmissionBrief } from "@/lib/types";


export function useDashboard() {
  return useQuery<DashboardResponse>({
    queryKey: ["me", "dashboard"],
    queryFn: async () => {
      const { data } = await api.get<DashboardResponse>("/me/dashboard");
      return data;
    },
    staleTime: 60_000,
  });
}


export function useMySubmissions(limit = 20) {
  return useQuery<SubmissionBrief[]>({
    queryKey: ["me", "submissions", limit],
    queryFn: async () => {
      const { data } = await api.get<SubmissionBrief[]>(`/me/submissions?limit=${limit}`);
      return data;
    },
  });
}
