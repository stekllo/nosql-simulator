/**
 * Кабинет преподавателя — список студентов.
 *
 * /teacher/students — таблица всех студентов, занимающихся на курсах преподавателя.
 * Клик по строке открывает детали /teacher/students/{id}.
 */
import { Link } from "react-router-dom";
import { Users, GraduationCap, BookOpen, TrendingUp, ArrowRight } from "lucide-react";

import { useTeacherStudents } from "@/hooks/useTeacher";
import type { StudentBrief } from "@/lib/types";


function formatDate(iso: string | null): string {
  if (!iso) return "никогда";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const days   = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (days === 0) return "сегодня";
  if (days === 1) return "вчера";
  if (days < 7)   return `${days} дн. назад`;
  if (days < 30)  return `${Math.floor(days / 7)} нед. назад`;
  return d.toLocaleDateString("ru-RU");
}

function accuracy(student: StudentBrief): number {
  if (student.total_attempts === 0) return 0;
  return Math.round((student.correct_attempts / student.total_attempts) * 100);
}


export function TeacherStudentsPage() {
  const { data, isLoading, error } = useTeacherStudents();

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8 text-sm text-slate-500">
        Загружаем список студентов…
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-4">
        Не удалось загрузить список студентов
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">

      <div className="flex items-baseline justify-between mb-6">
        <h1 className="text-[24px] font-semibold tracking-tight">Студенты</h1>
        <p className="text-sm text-slate-500">
          Прогресс студентов, занимающихся на ваших курсах.
        </p>
      </div>

      {/* ===== Сводные метрики ===== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard
          icon={<Users className="w-4 h-4" />}
          label="ВСЕГО СТУДЕНТОВ"
          value={data.total_students}
          color="blue"
        />
        <MetricCard
          icon={<TrendingUp className="w-4 h-4" />}
          label="АКТИВНЫХ ЗА НЕДЕЛЮ"
          value={data.active_this_week}
          color="emerald"
        />
        <MetricCard
          icon={<BookOpen className="w-4 h-4" />}
          label="ВАШИХ КУРСОВ"
          value={data.teacher_courses}
          color="amber"
        />
        <MetricCard
          icon={<GraduationCap className="w-4 h-4" />}
          label="СРЕДНИЙ БАЛЛ"
          value={data.average_score}
          color="violet"
        />
      </div>

      {/* ===== Таблица студентов ===== */}
      {data.students.length === 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 p-12 text-center">
          <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-[15px] font-medium text-slate-700 mb-1">Студентов пока нет</h3>
          <p className="text-sm text-slate-500">
            Когда студенты начнут решать задания на ваших курсах, они появятся здесь.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Студент</th>
                <th className="px-4 py-3 text-center">Курсов начато</th>
                <th className="px-4 py-3 text-center">Попыток</th>
                <th className="px-4 py-3 text-center">Точность</th>
                <th className="px-4 py-3 text-center">Баллы</th>
                <th className="px-4 py-3 text-left">Активность</th>
                <th className="px-4 py-3 w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.students.map((s) => (
                <StudentRow key={s.user_id} student={s} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// ============ Sub-components ============

interface MetricCardProps {
  icon:  React.ReactNode;
  label: string;
  value: number;
  color: "blue" | "emerald" | "amber" | "violet";
}

function MetricCard({ icon, label, value, color }: MetricCardProps) {
  const colorMap = {
    blue:    "text-blue-600    bg-blue-50",
    emerald: "text-emerald-600 bg-emerald-50",
    amber:   "text-amber-600   bg-amber-50",
    violet:  "text-violet-600  bg-violet-50",
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
        <span className={`w-6 h-6 rounded flex items-center justify-center ${colorMap[color]}`}>
          {icon}
        </span>
        {label}
      </div>
      <div className="text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}


function StudentRow({ student }: { student: StudentBrief }) {
  const acc = accuracy(student);
  const accColor =
    acc >= 80 ? "text-emerald-600" :
    acc >= 50 ? "text-amber-600"   :
                "text-slate-400";

  const initials = (student.display_name || student.login)
    .split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <tr className="hover:bg-slate-50 cursor-pointer group">
      <td className="px-4 py-3">
        <Link to={`/teacher/students/${student.user_id}`} className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-medium">
            {initials}
          </div>
          <div>
            <div className="text-sm font-medium text-slate-900 group-hover:text-blue-600">
              {student.display_name || student.login}
            </div>
            <div className="text-[11px] text-slate-500">{student.email}</div>
          </div>
        </Link>
      </td>
      <td className="px-4 py-3 text-center text-sm text-slate-700">
        {student.courses_started}
      </td>
      <td className="px-4 py-3 text-center text-sm text-slate-700">
        {student.total_attempts}
      </td>
      <td className="px-4 py-3 text-center text-sm font-medium">
        <span className={accColor}>
          {student.total_attempts > 0 ? `${acc}%` : "—"}
        </span>
      </td>
      <td className="px-4 py-3 text-center text-sm font-semibold text-slate-900">
        {student.total_score}
      </td>
      <td className="px-4 py-3 text-sm text-slate-500">
        {formatDate(student.last_activity_at)}
      </td>
      <td className="px-4 py-3">
        <Link to={`/teacher/students/${student.user_id}`}
              className="text-slate-400 group-hover:text-blue-600">
          <ArrowRight className="w-4 h-4" />
        </Link>
      </td>
    </tr>
  );
}
