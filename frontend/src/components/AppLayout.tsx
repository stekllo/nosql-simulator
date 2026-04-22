/** Общий layout: top-bar сверху, контент снизу.
 *
 * Top-bar повторяет дизайн из макетов ВКР: синий логотип, навигация,
 * аватар с инициалами справа и выпадающее меню с выходом.
 */
import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { LogOut, User as UserIcon } from "lucide-react";

import { useAuthStore } from "@/stores/auth";
import { useMe } from "@/hooks/useAuth";


function initials(name: string | null | undefined, login: string): string {
  const base = name?.trim() || login;
  const parts = base.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return base.slice(0, 2).toUpperCase();
}

const roleLabel: Record<string, string> = {
  student: "Студент",
  teacher: "Преподаватель",
  admin:   "Администратор",
};

const roleBadgeColor: Record<string, string> = {
  student: "bg-blue-100   text-blue-800",
  teacher: "bg-amber-100  text-amber-800",
  admin:   "bg-rose-100   text-rose-800",
};


export function AppLayout() {
  const navigate     = useNavigate();
  const logoutStore  = useAuthStore((s) => s.logout);
  const storedUser   = useAuthStore((s) => s.user);
  const { data: me } = useMe();
  const user         = me ?? storedUser;

  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = () => {
    logoutStore();
    navigate("/login", { replace: true });
  };

  const navLinkCls = ({ isActive }: { isActive: boolean }) =>
    "px-3 py-1.5 rounded text-sm " +
    (isActive
      ? "bg-gray-100 font-medium text-gray-900"
      : "text-gray-600 hover:bg-gray-100");

  return (
    <div className="min-h-screen bg-slate-50">

      <header className="bg-white border-b border-gray-200 h-14 flex items-center px-6 sticky top-0 z-10">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
            N
          </div>
          <span className="font-semibold text-[15px]">NoSQL Simulator</span>
        </Link>

        <nav className="ml-8 flex items-center gap-1">
          <NavLink to="/"          className={navLinkCls} end>Каталог</NavLink>
          <NavLink to="/learning"  className={navLinkCls}>Обучение</NavLink>
          <NavLink to="/profile"   className={navLinkCls}>Личный кабинет</NavLink>
        </nav>

        <div className="ml-auto relative">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2.5 p-1 rounded hover:bg-gray-50"
          >
            <div className="text-right leading-tight hidden sm:block">
              <div className="text-sm font-medium text-gray-900">
                {user?.display_name || user?.login || "…"}
              </div>
              {user && (
                <span className={"inline-block text-[10px] px-1.5 py-0.5 rounded font-medium " + roleBadgeColor[user.role]}>
                  {roleLabel[user.role]}
                </span>
              )}
            </div>
            <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-medium">
              {initials(user?.display_name ?? null, user?.login ?? "?")}
            </div>
          </button>

          {menuOpen && (
            <>
              <div
                className="fixed inset-0 z-10"
                onClick={() => setMenuOpen(false)}
              />
              <div className="absolute right-0 top-full mt-1 w-52 bg-white rounded-md border border-gray-200 shadow-lg py-1 z-20">
                <Link
                  to="/profile"
                  onClick={() => setMenuOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  <UserIcon className="w-4 h-4" />
                  Профиль
                </Link>
                <div className="h-px bg-gray-100 my-1" />
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 text-sm text-rose-700 hover:bg-rose-50"
                >
                  <LogOut className="w-4 h-4" />
                  Выйти
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      <main>
        <Outlet />
      </main>
    </div>
  );
}
