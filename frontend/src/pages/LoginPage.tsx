import { useForm } from "react-hook-form";
import { Link, useNavigate, useLocation } from "react-router-dom";

import { useLogin } from "@/hooks/useAuth";
import { extractErrorMessage } from "@/lib/api";


interface LoginForm { username: string; password: string }


export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname?: string } } };
  const redirect = location.state?.from?.pathname ?? "/";

  const login = useLogin();
  const {
    register, handleSubmit, formState: { errors },
  } = useForm<LoginForm>();

  const onSubmit = async (values: LoginForm) => {
    try {
      await login.mutateAsync(values);
      navigate(redirect, { replace: true });
    } catch {
      // Ошибка отобразится через login.error ниже.
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-sm">

        <div className="flex items-center justify-center gap-2 mb-6">
          <div className="w-10 h-10 rounded-md bg-blue-600 text-white flex items-center justify-center font-bold text-lg">
            N
          </div>
          <span className="text-xl font-semibold">NoSQL Simulator</span>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
          <h1 className="text-lg font-semibold mb-1">Вход в систему</h1>
          <p className="text-sm text-slate-500 mb-5">Введите логин и пароль, чтобы продолжить обучение.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Логин</label>
              <input
                type="text"
                autoFocus
                autoComplete="username"
                {...register("username", { required: "Введите логин" })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
              />
              {errors.username && (
                <p className="text-xs text-rose-600 mt-1">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Пароль</label>
              <input
                type="password"
                autoComplete="current-password"
                {...register("password", { required: "Введите пароль" })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
              />
              {errors.password && (
                <p className="text-xs text-rose-600 mt-1">{errors.password.message}</p>
              )}
            </div>

            {login.isError && (
              <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-2.5">
                {extractErrorMessage(login.error)}
              </div>
            )}

            <button
              type="submit"
              disabled={login.isPending}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium rounded"
            >
              {login.isPending ? "Вход…" : "Войти"}
            </button>
          </form>

          <div className="mt-4 text-sm text-center text-slate-600">
            Нет аккаунта? <Link to="/register" className="text-blue-600 hover:underline">Создайте</Link>
          </div>
        </div>

        <div className="mt-4 text-[11px] text-slate-400 text-center leading-relaxed">
          Демо-аккаунты: <span className="font-mono">yuri / teacher123</span> · <span className="font-mono">student / student123</span>
        </div>

      </div>
    </div>
  );
}
