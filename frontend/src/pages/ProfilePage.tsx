import { useMe } from "@/hooks/useAuth";


const roleLabel: Record<string, string> = {
  student: "Студент",
  teacher: "Преподаватель",
  admin:   "Администратор",
};


export function ProfilePage() {
  const { data: user, isLoading } = useMe();

  if (isLoading) {
    return <div className="max-w-3xl mx-auto px-6 py-10 text-sm text-slate-500">Загрузка…</div>;
  }
  if (!user) return null;

  const rows: Array<[string, string]> = [
    ["ID пользователя",   String(user.user_id)],
    ["Логин",             user.login],
    ["Email",             user.email],
    ["Отображаемое имя",  user.display_name ?? "—"],
    ["Роль",              roleLabel[user.role] ?? user.role],
    ["Зарегистрирован",   new Date(user.created_at).toLocaleString("ru-RU")],
  ];

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-[22px] font-semibold tracking-tight">Профиль</h1>
      <p className="text-sm text-slate-500 mt-1">Данные вашей учётной записи.</p>

      <div className="mt-6 bg-white rounded-lg border border-slate-200">
        <dl className="divide-y divide-slate-100">
          {rows.map(([label, value]) => (
            <div key={label} className="grid grid-cols-[200px_1fr] px-5 py-3 text-sm">
              <dt className="text-slate-500">{label}</dt>
              <dd className="text-slate-900 font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
