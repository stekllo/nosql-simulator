/** Hooks для эндпоинтов /teacher (кабинет преподавателя). */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { StudentDetailResponse, TeacherStudentsResponse } from "@/lib/types";


/** Список всех студентов с прогрессом. */
export function useTeacherStudents() {
  return useQuery<TeacherStudentsResponse>({
    queryKey: ["teacher", "students"],
    queryFn: async () => {
      const { data } = await api.get<TeacherStudentsResponse>("/teacher/students");
      return data;
    },
  });
}


/** Детали одного студента. */
export function useStudentDetail(userId: number | string | undefined) {
  const id = Number(userId);
  return useQuery<StudentDetailResponse>({
    queryKey: ["teacher", "student", id],
    enabled:  Number.isFinite(id) && id > 0,
    queryFn:  async () => {
      const { data } = await api.get<StudentDetailResponse>(`/teacher/students/${id}`);
      return data;
    },
  });
}
