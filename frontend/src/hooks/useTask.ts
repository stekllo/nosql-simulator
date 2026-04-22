/** Hooks для /tasks эндпоинтов. */
import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  LessonDetail, RunRequest, RunResponse, SubmitResponse,
} from "@/lib/types";


export function useRunQuery(taskId: number) {
  return useMutation<RunResponse, unknown, RunRequest>({
    mutationFn: async (body) => {
      const { data } = await api.post<RunResponse>(`/tasks/${taskId}/run`, body);
      return data;
    },
  });
}

export function useSubmitQuery(taskId: number) {
  return useMutation<SubmitResponse, unknown, RunRequest>({
    mutationFn: async (body) => {
      const { data } = await api.post<SubmitResponse>(`/tasks/${taskId}/submit`, body);
      return data;
    },
  });
}

export function useLessonByTask(taskId: number | string | undefined) {
  const id = Number(taskId);
  return useQuery<LessonDetail>({
    queryKey: ["lesson-by-task", id],
    queryFn: async () => {
      const { data } = await api.get<LessonDetail>(`/tasks/${id}/lesson`);
      return data;
    },
    enabled: Number.isFinite(id) && id > 0,
  });
}
