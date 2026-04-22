/**
 * Личный кабинет студента (Рис. 2.7 из ВКР).
 *
 * 4 KPI-карточки сверху → гистограмма активности → курсы → достижения.
 * Данные приходят из /me/dashboard — реальные, из submissions.
 */
import { Link } from "react-router-dom";
import {
  Award,
  BookOpen,
  Flame,
  Target,
  Trophy,
  ChevronRight,
} from "lucide-react";

import { useMe } from "@/hooks/useAuth";
import { useDashboard, useMySubmissions } from "@/hooks/useMe";
import { nosqlTypeBadge, nosqlTypeLabel } from "@/lib/nosqlType";
import type { DashboardResponse } from "@/lib/types";

export function DashboardPage() {
  const { data: user } = useMe();
  const { data: dash, isLoading } = useDashboard();
  const { data: subs } = useMySubmissions(5);

  if (isLoading || !dash) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-10 text-sm text-slate-500">
        Загрузка…
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      {/* Приветствие */}
      <header className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-[24px] font-semibold tracking-tight">
            Личный кабинет
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            С возвращением{user?.display_name ? `, ${user.display_name}` : ""}.
            Продолжайте учиться каждый день.
          </p>
        </div>
        <div className="text-xs text-slate-500">
          Сегодня:{" "}
          <b className="text-slate-900">
            {new Date().toLocaleDateString("ru-RU", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </b>
        </div>
      </header>

      {/* KPI карточки */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          icon={<BookOpen className="w-4 h-4 text-blue-600" />}
          label="Активные курсы"
          value={dash.active_courses}
          caption={`из ${dash.total_courses} доступных`}
          tint="blue"
        />
        <KpiCard
          icon={<Target className="w-4 h-4 text-emerald-600" />}
          label="Решено заданий"
          value={dash.solved_tasks}
          caption={`из ${dash.available_tasks} · +${dash.weekly_delta} за неделю`}
          tint="emerald"
        />
        <KpiCard
          icon={<Trophy className="w-4 h-4 text-amber-600" />}
          label="Баллы"
          value={dash.total_score}
          caption={`+${dash.recent_score} за неделю`}
          tint="amber"
        />
        <KpiCard
          icon={<Flame className="w-4 h-4 text-rose-600" />}
          label="Серия дней"
          value={dash.streak_days}
          caption={`рекорд: ${dash.best_streak}`}
          tint="rose"
        />
      </div>

      {/* Основная сетка */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Левая (шире): активность + курсы */}
        <div className="lg:col-span-2 space-y-5">
          {/* Активность 30 дней */}
          <section className="bg-white rounded-lg border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[15px] font-semibold">
                Активность за 30 дней
              </h2>
              <span className="text-xs text-slate-500">
                {dateRange(dash.activity)}
              </span>
            </div>
            <ActivityChart activity={dash.activity} />
            <div className="flex items-center gap-4 mt-3 text-[11px] text-slate-500">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded bg-emerald-500" /> Правильные
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded bg-rose-400" /> Неправильные
              </span>
            </div>
          </section>

          {/* Курсы в процессе */}
          <section className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-[15px] font-semibold mb-4">Мои курсы</h2>
            {dash.current_courses.length === 0 && (
              <div className="text-sm text-slate-500">
                Ещё не приступили ни к одному курсу.{" "}
                <Link to="/" className="text-blue-600 hover:underline">
                  Открыть каталог →
                </Link>
              </div>
            )}
            <div className="space-y-3">
              {dash.current_courses.map((c) => (
                <Link
                  key={c.course_id}
                  to={`/courses/${c.course_id}`}
                  className="block border border-slate-200 rounded-md p-4 hover:border-slate-300 hover:shadow-sm transition"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span
                      className={
                        "inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded border font-mono " +
                        nosqlTypeBadge[c.nosql_type]
                      }
                    >
                      {nosqlTypeLabel[c.nosql_type]}
                    </span>
                    <span className="text-xs text-slate-500">
                      {c.lessons_done} / {c.lesson_count} уроков
                    </span>
                    <span className="ml-auto text-xs text-slate-500">
                      {c.total_score}{" "}
                      <span className="text-slate-400">баллов</span>
                    </span>
                  </div>
                  <div className="text-[14px] font-medium text-slate-900">
                    {c.course_title}
                  </div>

                  <div className="mt-2.5 h-1.5 bg-slate-100 rounded overflow-hidden">
                    <div
                      className="h-full bg-blue-500 transition-all"
                      style={{ width: `${Math.min(c.percent, 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-[11px] text-slate-500">
                      {c.percent.toFixed(0)}%
                    </span>
                    <span className="text-[11px] text-blue-600 flex items-center gap-0.5">
                      Продолжить <ChevronRight className="w-3 h-3" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </section>
        </div>

        {/* Правая: достижения + история */}
        <div className="space-y-5">
          <section className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-[15px] font-semibold mb-4 flex items-center gap-2">
              <Award className="w-4 h-4 text-amber-500" />
              Достижения
            </h2>
            <div className="space-y-2">
              {dash.achievements.map((a) => (
                <div
                  key={a.achievement_id}
                  className={
                    "flex items-center gap-3 p-2.5 rounded border " +
                    (a.granted
                      ? "bg-amber-50/60 border-amber-200"
                      : "bg-slate-50 border-slate-200 opacity-60")
                  }
                >
                  <div className="text-xl w-7 text-center">
                    {a.icon ?? "🏅"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-medium text-slate-900 truncate">
                      {a.name}
                    </div>
                    {a.description && (
                      <div className="text-[11px] text-slate-500 truncate">
                        {a.description}
                      </div>
                    )}
                  </div>
                  <div className="text-[11px] font-medium text-slate-500">
                    +{a.points}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Недавние попытки */}
          {subs && subs.length > 0 && (
            <section className="bg-white rounded-lg border border-slate-200 p-5">
              <h2 className="text-[15px] font-semibold mb-3">
                Последние попытки
              </h2>
              <ul className="divide-y divide-slate-100">
                {subs.map((s) => (
                  <li key={s.submission_id}>
                    <Link
                      to={`/tasks/${s.task_id}`}
                      className="flex items-start gap-2 py-2 hover:bg-slate-50 -mx-2 px-2 rounded"
                    >
                      <span
                        className={
                          "mt-1 w-1.5 h-1.5 rounded-full " +
                          (s.status === "correct"
                            ? "bg-emerald-500"
                            : s.status === "timeout"
                              ? "bg-amber-500"
                              : "bg-rose-500")
                        }
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-[12px] text-slate-900 font-medium truncate">
                          {s.lesson_title}
                        </div>
                        <div className="text-[11px] text-slate-500 truncate">
                          {s.course_title}
                        </div>
                      </div>
                      <div className="text-[11px] text-slate-500 whitespace-nowrap">
                        {formatRelative(s.submitted_at)}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

// ==================== Sub-components ====================

function KpiCard({
  icon,
  label,
  value,
  caption,
  tint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  caption: string;
  tint: "blue" | "emerald" | "amber" | "rose";
}) {
  const bg = {
    blue: "bg-blue-50",
    emerald: "bg-emerald-50",
    amber: "bg-amber-50",
    rose: "bg-rose-50",
  }[tint];

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2">
        <div
          className={`w-7 h-7 rounded-md ${bg} flex items-center justify-center`}
        >
          {icon}
        </div>
        <div className="text-[11px] uppercase tracking-wider text-slate-500 font-medium">
          {label}
        </div>
      </div>
      <div className="text-[28px] font-semibold tracking-tight mt-2 leading-none">
        {value}
      </div>
      <div className="text-[11px] text-slate-500 mt-1">{caption}</div>
    </div>
  );
}

function ActivityChart({
  activity,
}: {
  activity: DashboardResponse["activity"];
}) {
  const max = Math.max(1, ...activity.map((d) => d.correct + d.wrong));

  return (
    <div className="h-36 flex items-end gap-[3px]">
      {activity.map((d) => {
        const total = d.correct + d.wrong;
        const totalPct = total === 0 ? 2 : (total / max) * 100;
        const corrPct = total === 0 ? 0 : (d.correct / total) * 100;
        const wrPct = total === 0 ? 0 : (d.wrong / total) * 100;

        return (
          <div
            key={d.day}
            className="flex-1 h-full flex items-end"
            title={`${d.day}: ${d.correct} ✓ / ${d.wrong} ✗`}
          >
            <div
              className="w-full flex flex-col-reverse rounded-t-[2px] overflow-hidden"
              style={{ height: `${totalPct}%` }}
            >
              {total > 0 ? (
                <>
                  <div
                    style={{ height: `${corrPct}%` }}
                    className="bg-emerald-500"
                  />
                  <div
                    style={{ height: `${wrPct}%` }}
                    className="bg-rose-400"
                  />
                </>
              ) : (
                <div className="h-full bg-slate-200" />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ==================== helpers ====================

function dateRange(activity: DashboardResponse["activity"]): string {
  if (activity.length === 0) return "";
  const first = new Date(activity[0].day);
  const last = new Date(activity[activity.length - 1].day);
  const fmt = (d: Date) =>
    d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  return `${fmt(first)} — ${fmt(last)}`;
}

function formatRelative(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diff = Math.max(0, now - then);
  const min = Math.floor(diff / 60000);
  if (min < 1) return "только что";
  if (min < 60) return `${min} мин`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ч`;
  const days = Math.floor(hr / 24);
  if (days < 30) return `${days} дн`;
  return new Date(iso).toLocaleDateString("ru-RU");
}
