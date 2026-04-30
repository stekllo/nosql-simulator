import { useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Shield, GraduationCap, User as UserIcon, Search, CheckCircle2, AlertTriangle } from "lucide-react";

import { useAdminUsers, useChangeUserRole } from "@/hooks/useAdmin";
import { useAuthStore } from "@/stores/auth";
import type { UserRole, AdminUserBrief } from "@/lib/types";


// ---------- Отображение роли как бейдж ----------

const ROLE_LABEL: Record<UserRole, string> = {
  student: "Студент",
  teacher: "Преподаватель",
  admin:   "Администратор",
};

// Множественное число — для UI-фильтра «Студенты (5)», «Преподаватели (1)» и т.д.
const ROLE_LABEL_PLURAL: Record<UserRole, string> = {
  student: "Студенты",
  teacher: "Преподаватели",
  admin:   "Администраторы",
};

const ROLE_BADGE: Record<UserRole, string> = {
  student: "bg-slate-100  text-slate-700",
  teacher: "bg-blue-50    text-blue-700",
  admin:   "bg-purple-50  text-purple-700",
};

const ROLE_ICON = {
  student: UserIcon,
  teacher: GraduationCap,
  admin:   Shield,
};


export function AdminUsersPage() {
  const me           = useAuthStore(s => s.user);
  const [filter,   setFilter]   = useState<UserRole | null>(null);
  const [search,   setSearch]   = useState("");
  const [feedback, setFeedback] = useState<
    { kind: "ok" | "err"; text: string } | null
  >(null);

  const { data, isLoading, isError } = useAdminUsers(filter);
  const changeRole = useChangeUserRole();

  if (isLoading) {
    return <div className="max-w-6xl mx-auto px-6 py-10 text-sm text-slate-500">Загрузка пользователей…</div>;
  }
  if (isError || !data) {
    return <div className="max-w-6xl mx-auto px-6 py-10 text-sm text-rose-700">Ошибка загрузки.</div>;
  }

  // Локальный поиск по логину/имени.
  const filteredUsers = data.users.filter(u => {
    if (!search.trim()) return true;
    const needle = search.trim().toLowerCase();
    return (
      u.login.toLowerCase().includes(needle) ||
      (u.display_name ?? "").toLowerCase().includes(needle) ||
      u.email.toLowerCase().includes(needle)
    );
  });

  const handleRoleChange = async (user: AdminUserBrief, newRole: UserRole) => {
    if (newRole === user.role) return;
    setFeedback(null);
    try {
      const res = await changeRole.mutateAsync({ userId: user.user_id, role: newRole });
      setFeedback({
        kind: "ok",
        text: `Роль пользователя «${user.login}» изменена: ${ROLE_LABEL[res.old_role]} → ${ROLE_LABEL[res.new_role]}`,
      });
    } catch (e: unknown) {
      const message = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "Не удалось изменить роль";
      setFeedback({ kind: "err", text: message });
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
        ← На главную
      </Link>

      <h1 className="text-2xl font-semibold mt-4 mb-1">Пользователи</h1>
      <p className="text-sm text-slate-500">
        Всего {data.by_role.student} студентов, {data.by_role.teacher} преподавателей, {data.by_role.admin} администраторов.
      </p>

      {/* Feedback-баннер */}
      {feedback && (
        <div
          className={
            "mt-4 flex items-start gap-2 px-4 py-3 rounded-md border text-sm " +
            (feedback.kind === "ok"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800")
          }
        >
          {feedback.kind === "ok" ? (
            <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
          ) : (
            <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          )}
          <span>{feedback.text}</span>
          <button
            type="button"
            onClick={() => setFeedback(null)}
            className="ml-auto text-xs opacity-60 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      )}

      {/* Фильтры */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <div className="flex gap-1 bg-slate-100 rounded-md p-1">
          {([null, "student", "teacher", "admin"] as const).map(r => (
            <button
              key={r ?? "all"}
              type="button"
              onClick={() => setFilter(r)}
              className={
                "px-3 py-1.5 text-sm rounded font-medium transition-colors " +
                (filter === r
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900")
              }
            >
              {r === null
                ? `Все (${data.by_role.student + data.by_role.teacher + data.by_role.admin})`
                : `${ROLE_LABEL_PLURAL[r]} (${data.by_role[r]})`}
            </button>
          ))}
        </div>

        <div className="flex-1 max-w-xs ml-auto relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Поиск по логину, имени, email"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:border-blue-400"
          />
        </div>
      </div>

      {/* Таблица */}
      <div className="mt-4 bg-white border border-slate-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="text-left  px-4 py-3 font-medium">Логин / Имя</th>
              <th className="text-left  px-4 py-3 font-medium">Email</th>
              <th className="text-left  px-4 py-3 font-medium">Роль</th>
              <th className="text-left  px-4 py-3 font-medium">Зарегистрирован</th>
              <th className="text-right px-4 py-3 font-medium">Сменить роль</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center text-slate-500 py-8">
                  Ничего не найдено.
                </td>
              </tr>
            ) : (
              filteredUsers.map(u => {
                const Icon = ROLE_ICON[u.role];
                const isMe = me?.user_id === u.user_id;

                return (
                  <tr key={u.user_id} className="border-b last:border-b-0 border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{u.login}</div>
                      {u.display_name && (
                        <div className="text-xs text-slate-500">{u.display_name}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{u.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium " +
                          ROLE_BADGE[u.role]
                        }
                      >
                        <Icon className="w-3 h-3" />
                        {ROLE_LABEL[u.role]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      {new Date(u.created_at).toLocaleDateString("ru-RU")}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isMe ? (
                        <span className="text-xs text-slate-400">это вы</span>
                      ) : (
                        <select
                          value={u.role}
                          onChange={e => handleRoleChange(u, e.target.value as UserRole)}
                          disabled={changeRole.isPending}
                          className="text-xs px-2 py-1 border border-slate-300 rounded focus:outline-none focus:border-blue-400 disabled:opacity-60"
                        >
                          <option value="student">Студент</option>
                          <option value="teacher">Преподаватель</option>
                          <option value="admin">Администратор</option>
                        </select>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Подсказка про самоблокировку */}
      <p className="mt-4 text-xs text-slate-500 italic">
        Для безопасности нельзя сменить собственную роль через интерфейс — иначе можно
        случайно потерять доступ к админке. Если такая операция нужна, обратитесь к
        другому администратору или выполните её через прямой SQL-запрос.
      </p>

      {changeRole.isPending && (
        <div className="fixed top-4 right-4 bg-white border border-slate-200 rounded-md px-4 py-2 shadow-md flex items-center gap-2 text-sm text-slate-700">
          <Loader2 className="w-4 h-4 animate-spin" />
          Меняю роль…
        </div>
      )}
    </div>
  );
}
