/** React Query hooks для эндпоинтов /courses. */
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  CourseBrief, CourseDetail, LessonDetail, NoSQLType,
} from "@/lib/types";


// ---------- Список курсов ----------

interface UseCoursesParams {
  nosqlType?: NoSQLType | null;
  authorId?:  number    | null;
}

export function useCourses(params: UseCoursesParams = {}) {
  const { nosqlType, authorId } = params;

  return useQuery<CourseBrief[]>({
    queryKey: ["courses", { nosqlType: nosqlType ?? null, authorId: authorId ?? null }],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (nosqlType) searchParams.set("nosql_type", nosqlType);
      if (authorId)  searchParams.set("author_id",  String(authorId));
      const qs = searchParams.toString();

      const { data } = await api.get<CourseBrief[]>(`/courses${qs ? `?${qs}` : ""}`);
      return data;
    },
  });
}


// ---------- Детали курса ----------

export function useCourse(courseId: number | string | undefined) {
  const id = Number(courseId);

  return useQuery<CourseDetail>({
    queryKey: ["courses", id],
    queryFn: async () => {
      const { data } = await api.get<CourseDetail>(`/courses/${id}`);
      return data;
    },
    enabled: Number.isFinite(id) && id > 0,
  });
}


// ---------- Урок ----------

export function useLesson(lessonId: number | string | undefined) {
  const id = Number(lessonId);

  return useQuery<LessonDetail>({
    queryKey: ["lessons", id],
    queryFn: async () => {
      const { data } = await api.get<LessonDetail>(`/courses/lessons/${id}`);
      return data;
    },
    enabled: Number.isFinite(id) && id > 0,
  });
}
