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

/** Прогресс конкретного пользователя по курсу. */
export interface CourseProgress {
  lessons_completed: number;
  lessons_total:     number;
  tasks_solved:      number;
  tasks_total:       number;
  percent:           number;
}

export interface CourseBrief {
  course_id:   number;
  title:       string;
  description: string | null;
  nosql_type:  NoSQLType;
  difficulty:  number | null;
  created_at:  string;
  author:      AuthorBrief;
  /** Прогресс текущего пользователя. null если в курсе вообще нет уроков. */
  progress:    CourseProgress | null;
}

export interface LessonBrief {
  lesson_id:    number;
  title:        string;
  order_num:    number;
  duration_min: number | null;
  task_count:   number;
  /** Урок пройден: все задания решены или у урока нет заданий. */
  is_completed: boolean;
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
  /** Решено ли это задание текущим пользователем (есть CORRECT submission). */
  is_solved: boolean;
}

export interface LessonDetail {
  lesson_id:    number;
  module_id:    number;
  title:        string;
  content_md:   string;
  order_num:    number;
  duration_min: number | null;
  tasks:        TaskBrief[];
  /** Урок пройден текущим пользователем. */
  is_completed: boolean;
  /** ID следующего урока в курсе, либо null если этот — последний. */
  next_lesson_id: number | null;
}

export interface LessonCompletionResponse {
  lesson_id:         number;
  /** True — повторный клик; false — отметка только что создана. */
  already_completed: boolean;
}


// ---------- Билдерское дерево курса (со списком заданий внутри уроков) ----------

export interface BuilderTaskBrief {
  task_id:    number;
  statement:  string;
  db_type:    NoSQLType;
  max_score:  number;
}

export interface BuilderLessonBrief {
  lesson_id:    number;
  title:        string;
  order_num:    number;
  duration_min: number | null;
  tasks:        BuilderTaskBrief[];
}

export interface BuilderModuleBrief {
  module_id:   number;
  title:       string;
  description: string | null;
  order_num:   number;
  lessons:     BuilderLessonBrief[];
}

export interface BuilderCourseDetail {
  course_id:   number;
  title:       string;
  description: string | null;
  nosql_type:  NoSQLType;
  difficulty:  number | null;
  created_at:  string;
  modules:     BuilderModuleBrief[];
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


// ---------- Dashboard ----------

export interface DailyActivity {
  day:     string;
  correct: number;
  wrong:   number;
}

export interface CourseProgress {
  course_id:    number;
  course_title: string;
  nosql_type:   NoSQLType;
  percent:      number;
  total_score:  number;
  module_count: number;
  lesson_count: number;
  lessons_done: number;
}

export interface AchievementBrief {
  achievement_id: number;
  name:           string;
  description:    string | null;
  icon:           string | null;
  points:         number;
  granted:        boolean;
  granted_at:     string | null;
}

export interface DashboardResponse {
  active_courses:  number;
  total_courses:   number;
  solved_tasks:    number;
  available_tasks: number;
  weekly_delta:    number;
  total_score:     number;
  recent_score:    number;
  streak_days:     number;
  best_streak:     number;
  activity:        DailyActivity[];
  current_courses: CourseProgress[];
  achievements:    AchievementBrief[];
}

export interface SubmissionBrief {
  submission_id: number;
  task_id:       number;
  is_correct:    boolean | null;
  score:         number  | null;
  status:        SubmissionStatus;
  submitted_at:  string;
  lesson_title:  string;
  course_title:  string;
}


// ---------- Конструктор ----------

export interface TaskCreate {
  statement:           string;
  db_type:             NoSQLType;
  fixture:             Record<string, unknown>;
  reference_solution:  string;
  reference_solutions?: string[];
  compare_ordered?:    boolean;
  max_score:           number;
  attempts_limit:      number;
}

export interface TaskOut {
  task_id:             number;
  lesson_id:           number;
  statement:           string;
  db_type:             NoSQLType;
  fixture:             Record<string, unknown>;
  reference_solution:  string;
  reference_solutions: string[];
  compare_ordered:     boolean;
  max_score:           number;
  attempts_limit:      number;
}

/** Пейлоад для обновления задания (PATCH /builder/tasks/{id}).
 *  db_type намеренно отсутствует — менять тип задания после создания нельзя. */
export interface TaskUpdatePayload {
  statement?:           string;
  fixture?:             Record<string, unknown>;
  reference_solution?:  string;
  reference_solutions?: string[];
  compare_ordered?:     boolean;
  max_score?:           number;
  attempts_limit?:      number;
}

export interface ReferenceDryRun {
  ok:          boolean;
  duration_ms: number;
  result?:     unknown;
  error?:      string | null;
}


// ---------- Конструктор уроков ----------

/** Полный вид урока для редактирования (GET /builder/lessons/{id}). */
export interface LessonForEdit {
  lesson_id:    number;
  module_id:    number;
  course_id:    number;
  title:        string;
  content_md:   string;
  order_num:    number;
  duration_min: number | null;
}

/** Пейлоад для создания урока (POST /builder/modules/{id}/lessons). */
export interface LessonCreatePayload {
  title:         string;
  content_md:    string;
  order_num:     number;
  duration_min?: number | null;
}

/** Пейлоад для обновления урока (PATCH /builder/lessons/{id}). */
export interface LessonUpdatePayload {
  title?:        string;
  content_md?:   string;
  order_num?:    number;
  duration_min?: number | null;
}


// ---------- Кабинет преподавателя ----------

export interface StudentBrief {
  user_id:           number;
  login:             string;
  display_name:      string | null;
  email:             string;
  total_attempts:    number;
  correct_attempts:  number;
  total_score:       number;
  courses_started:   number;
  last_activity_at:  string | null;
}

export interface TeacherStudentsResponse {
  students:          StudentBrief[];
  total_students:    number;
  active_this_week:  number;
  teacher_courses:   number;
  average_score:     number;
}

export interface StudentCourseProgress {
  course_id:        number;
  course_title:     string;
  nosql_type:       string;
  total_lessons:    number;
  total_tasks:      number;
  solved_tasks:     number;
  percent:          number;
  total_score:      number;
}

export interface StudentSubmission {
  submission_id:  number;
  task_id:        number;
  course_title:   string;
  lesson_title:   string;
  statement:      string;
  is_correct:     boolean | null;
  score:          number  | null;
  status:         string;
  submitted_at:   string;
}

export interface StudentDailyActivity {
  day:     string;
  correct: number;
  wrong:   number;
}

export interface StudentDetailResponse {
  user_id:            number;
  login:              string;
  display_name:       string | null;
  email:              string;
  total_attempts:     number;
  correct_attempts:   number;
  total_score:        number;
  courses_started:    number;
  last_activity_at:   string | null;
  course_progress:    StudentCourseProgress[];
  recent_submissions: StudentSubmission[];
  activity:           StudentDailyActivity[];
}
