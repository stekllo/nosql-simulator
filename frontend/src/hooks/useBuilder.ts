/** Hooks для /builder эндпоинтов. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  CourseBrief, CourseDetail, LessonCreatePayload, LessonForEdit,
  LessonUpdatePayload, ReferenceDryRun, TaskCreate, TaskOut,
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


// ---------- Урок: получить полный текст для редактирования ----------

export function useLessonForEdit(lessonId: number | string | undefined) {
  const id = Number(lessonId);
  return useQuery<LessonForEdit>({
    queryKey: ["builder", "lesson", id],
    queryFn: async () => {
      const { data } = await api.get<LessonForEdit>(`/builder/lessons/${id}`);
      return data;
    },
    enabled: Number.isFinite(id) && id > 0,
  });
}


// ---------- Урок: создать ----------

export function useCreateLesson(moduleId: number) {
  const qc = useQueryClient();
  return useMutation<{ lesson_id: number; title: string; order_num: number }, unknown, LessonCreatePayload>({
    mutationFn: async (body) => {
      const { data } = await api.post(`/builder/modules/${moduleId}/lessons`, body);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["builder"] });
      qc.invalidateQueries({ queryKey: ["courses"] });
    },
  });
}


// ---------- Урок: обновить ----------

export function useUpdateLesson(lessonId: number) {
  const qc = useQueryClient();
  return useMutation<LessonForEdit, unknown, LessonUpdatePayload>({
    mutationFn: async (body) => {
      const { data } = await api.patch<LessonForEdit>(`/builder/lessons/${lessonId}`, body);
      return data;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["builder", "lesson", lessonId] });
      qc.invalidateQueries({ queryKey: ["builder", "course", data.course_id] });
      qc.invalidateQueries({ queryKey: ["courses"] });
      // Студенческий кэш урока (LessonPage) тоже надо обновить.
      qc.invalidateQueries({ queryKey: ["lesson", lessonId] });
    },
  });
}


// ---------- Урок: удалить ----------

export function useDeleteLesson() {
  const qc = useQueryClient();
  return useMutation<void, unknown, number>({
    mutationFn: async (lessonId) => {
      await api.delete(`/builder/lessons/${lessonId}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["builder"] });
      qc.invalidateQueries({ queryKey: ["courses"] });
    },
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
