/** Типы, разделяемые фронтендом и дублирующие Pydantic-схемы бэкенда. */

export type UserRole  = "student" | "teacher" | "admin";
export type NoSQLType = "document" | "key_value" | "column" | "graph" | "mixed";

export type SubmissionStatus = "pending" | "correct" | "wrong" | "timeout";


export interface User {
  user_id:      number;
  login:        string;
  email:        string;
  display_name: string | null;
  role:         UserRole;
  created_at:   string;
}

export interface LoginResponse {
  access_token: string;
  token_type:   string;
}

export interface RegisterRequest {
  login:         string;
  email:         string;
  password:      string;
  display_name?: string;
}


// ---------- Курсы ----------

export interface AuthorBrief {
  user_id:      number;
  login:        string;
  display_name: string | null;
}

export interface CourseBrief {
  course_id:   number;
  title:       string;
  description: string | null;
  nosql_type:  NoSQLType;
  difficulty:  number | null;
  created_at:  string;
  author:      AuthorBrief;
}

export interface LessonBrief {
  lesson_id:    number;
  title:        string;
  order_num:    number;
  duration_min: number | null;
  task_count:   number;
}

export interface ModuleWithLessons {
  module_id:   number;
  title:       string;
  description: string | null;
  order_num:   number;
  lessons:     LessonBrief[];
}

export interface CourseDetail extends CourseBrief {
  modules: ModuleWithLessons[];
}

export interface TaskBrief {
  task_id:   number;
  statement: string;
  db_type:   NoSQLType;
  max_score: number;
}

export interface LessonDetail {
  lesson_id:    number;
  module_id:    number;
  title:        string;
  content_md:   string;
  order_num:    number;
  duration_min: number | null;
  tasks:        TaskBrief[];
}


// ---------- Запуск и проверка заданий ----------

export interface RunRequest {
  query_text: string;
}

export interface RunResponse {
  ok:          boolean;
  duration_ms: number;
  result?:     unknown;
  error?:      string | null;
}

export interface SubmitResponse {
  submission_id: number;
  is_correct:    boolean | null;
  score:         number  | null;
  status:        SubmissionStatus;
  duration_ms:   number;
  result?:       unknown;
  error?:        string | null;
  submitted_at:  string;
}
