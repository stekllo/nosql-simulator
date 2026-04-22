/** Hooks для /builder эндпоинтов. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  CourseBrief, CourseDetail, ReferenceDryRun, TaskCreate, TaskOut,
} from "@/lib/types";


// ---------- Мои курсы ----------

export function useMyCourses() {
  return useQuery<CourseBrief[]>({
    queryKey: ["builder", "courses"],
    queryFn: async () => {
      const { data } = await api.get<CourseBrief[]>("/builder/courses");
      return data;
    },
  });
}


// ---------- Курс в деталях (для редактирования) ----------

export function useBuilderCourse(courseId: number | string | undefined) {
  const id = Number(courseId);
  return useQuery<CourseDetail>({
    queryKey: ["builder", "course", id],
    queryFn: async () => {
      const { data } = await api.get<CourseDetail>(`/builder/courses/${id}`);
      return data;
    },
    enabled: Number.isFinite(id) && id > 0,
  });
}


// ---------- Проверка эталона ----------

export function useReferenceDryRun() {
  return useMutation<ReferenceDryRun, unknown, TaskCreate>({
    mutationFn: async (body) => {
      const { data } = await api.post<ReferenceDryRun>("/builder/reference-dry-run", body);
      return data;
    },
  });
}


// ---------- Создание задания ----------

export function useCreateTask(lessonId: number) {
  const qc = useQueryClient();
  return useMutation<TaskOut, unknown, TaskCreate>({
    mutationFn: async (body) => {
      const { data } = await api.post<TaskOut>(`/builder/lessons/${lessonId}/tasks`, body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["builder"] });
      qc.invalidateQueries({ queryKey: ["courses"] });
    },
  });
}
