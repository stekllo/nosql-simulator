/**
 * Кабинет преподавателя — детали одного студента.
 *
 * /teacher/students/{user_id}
 *  - метрики (попытки, точность, баллы, последняя активность)
 *  - прогресс по курсам с процентами
 *  - гистограмма активности за 30 дней
 *  - последние попытки (15 шт.)
 */
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, XCircle, Clock } from "lucide-react";

import { useStudentDetail } from "@/hooks/useTeacher";
import type { StudentSubmission } from "@/lib/types";


export function TeacherStudentDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const { data, isLoading, error } = useStudentDetail(userId);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8 text-sm text-slate-500">
        Загружаем профиль студента…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-8 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-4">
        Не удалось загрузить профиль студента
      </div>
    );
  }

  const accuracy = data.total_attempts > 0
    ? Math.round((data.correct_attempts / data.total_attempts) * 100)
    : 0;

  const initials = (data.display_name || data.login)
    .split(/\s+/).map(p => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">

      <Link to="/teacher/students" className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 mb-4">
        <ArrowLeft className="w-4 h-4" />
        К списку студентов
      </Link>

      {/* ===== Шапка ===== */}
      <div className="flex items-center gap-4 mb-6">
        <div className="w-14 h-14 rounded-full bg-blue-600 text-white flex items-center justify-center text-lg font-medium">
          {initials}
        </div>
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight">
            {data.display_name || data.login}
          </h1>
          <p className="text-sm text-slate-500">
            {data.email} · логин <code className="font-mono">{data.login}</code>
          </p>
        </div>
      </div>

      {/* ===== Метрики ===== */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <MetricCard label="ПОПЫТОК" value={data.total_attempts} />
        <MetricCard label="ТОЧНОСТЬ" value={data.total_attempts > 0 ? `${accuracy}%` : "—"} />
        <MetricCard label="БАЛЛЫ" value={data.total_score} />
        <MetricCard label="КУРСОВ НАЧАТО" value={data.courses_started} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,420px)] gap-6">

        {/* ===== Левая колонка: курсы и попытки ===== */}
        <div className="space-y-6">

          {/* Прогресс по курсам */}
          <section className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">
              Прогресс по курсам
            </h2>
            {data.course_progress.length === 0 ? (
              <p className="text-sm text-slate-400">Студент ещё не начал ни одного курса</p>
            ) : (
              <div className="space-y-4">
                {data.course_progress.map((c) => (
                  <div key={c.course_id}>
                    <div className="flex items-baseline justify-between mb-1.5">
                      <div className="text-sm font-medium text-slate-900">{c.course_title}</div>
                      <div className="text-xs text-slate-500">
                        {c.solved_tasks} / {c.total_tasks} задач · {c.total_score} баллов
                      </div>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-600 rounded-full transition-all"
                        style={{ width: `${c.percent}%` }}
                      />
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1">{c.percent}%</div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Последние попытки */}
          <section className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">
              Последние попытки
            </h2>
            {data.recent_submissions.length === 0 ? (
              <p className="text-sm text-slate-400">Пока нет попыток</p>
            ) : (
              <div className="space-y-2.5">
                {data.recent_submissions.map((s) => (
                  <SubmissionRow key={s.submission_id} sub={s} />
                ))}
              </div>
            )}
          </section>
        </div>

        {/* ===== Правая колонка: активность ===== */}
        <div className="space-y-6">

          {/* Гистограмма активности */}
          <section className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">
              Активность за 30 дней
            </h2>
            {data.activity.length === 0 ? (
              <p className="text-sm text-slate-400">Активности не было</p>
            ) : (
              <ActivityChart activity={data.activity} />
            )}
          </section>
        </div>
      </div>
    </div>
  );
}


// ============ Sub-components ============

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
        {label}
      </div>
      <div className="text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}


function SubmissionRow({ sub }: { sub: StudentSubmission }) {
  const isCorrect = sub.is_correct === true;
  const isTimeout = sub.status === "timeout";

  const Icon = isCorrect ? CheckCircle2 : isTimeout ? Clock : XCircle;
  const color = isCorrect ? "text-emerald-600" : isTimeout ? "text-amber-600" : "text-rose-500";

  return (
    <div className="flex items-start gap-2.5 text-sm">
      <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${color}`} />
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-slate-500 mb-0.5">
          {sub.course_title} · {sub.lesson_title}
        </div>
        <div className="text-slate-700 truncate" title={sub.statement}>
          {sub.statement}
        </div>
        <div className="text-[11px] text-slate-400 mt-0.5">
          {new Date(sub.submitted_at).toLocaleString("ru-RU", {
            day: "numeric",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
          })}
          {isCorrect && sub.score != null && ` · +${sub.score} баллов`}
        </div>
      </div>
    </div>
  );
}


function ActivityChart({ activity }: { activity: { day: string; correct: number; wrong: number }[] }) {
  if (activity.length === 0) return null;

  const maxValue = Math.max(...activity.map(a => a.correct + a.wrong), 1);
  const totalCorrect = activity.reduce((sum, a) => sum + a.correct, 0);
  const totalWrong   = activity.reduce((sum, a) => sum + a.wrong,   0);

  return (
    <div>
      <div className="flex items-end gap-1 h-32 mb-3">
        {activity.map((day, idx) => {
          const total       = day.correct + day.wrong;
          const totalH      = (total / maxValue) * 100;
          const correctH    = total > 0 ? (day.correct / total) * totalH : 0;
          const wrongH      = total > 0 ? (day.wrong   / total) * totalH : 0;

          return (
            <div key={idx} className="flex-1 flex flex-col justify-end gap-px" title={`${day.day}: ${day.correct} верных, ${day.wrong} неверных`}>
              {wrongH > 0 && (
                <div className="bg-rose-400 rounded-t-sm" style={{ height: `${wrongH}%` }} />
              )}
              {correctH > 0 && (
                <div className={`bg-emerald-500 ${wrongH === 0 ? "rounded-t-sm" : ""}`}
                     style={{ height: `${correctH}%` }} />
              )}
            </div>
          );
        })}
      </div>
      <div className="flex items-center justify-between text-[11px] text-slate-500">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" />
            {totalCorrect} верных
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-400" />
            {totalWrong} неверных
          </span>
        </div>
        <span>{activity.length} дн.</span>
      </div>
    </div>
  );
}
