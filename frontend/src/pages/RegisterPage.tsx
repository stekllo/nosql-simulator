import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";

import { useRegister } from "@/hooks/useAuth";
import { extractErrorMessage } from "@/lib/api";
import type { RegisterRequest } from "@/lib/types";


export function RegisterPage() {
  const navigate = useNavigate();
  const reg      = useRegister();

  const {
    register, handleSubmit, formState: { errors },
  } = useForm<RegisterRequest>();

  const onSubmit = async (values: RegisterRequest) => {
    try {
      await reg.mutateAsync(values);
      navigate("/", { replace: true });
    } catch {
      /* отобразится через reg.error */
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-sm">

        <div className="flex items-center justify-center gap-2 mb-6">
          <div className="w-10 h-10 rounded-md bg-blue-600 text-white flex items-center justify-center font-bold text-lg">
            N
          </div>
          <span className="text-xl font-semibold">NoSQL Simulator</span>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
          <h1 className="text-lg font-semibold mb-1">Регистрация</h1>
          <p className="text-sm text-slate-500 mb-5">Создайте учётную запись студента.</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Логин</label>
              <input
                autoFocus autoComplete="username"
                {...register("login", {
                  required:  "Введите логин",
                  minLength: { value: 3,  message: "Минимум 3 символа" },
                  maxLength: { value: 64, message: "Максимум 64 символа" },
                  pattern:   { value: /^[a-zA-Z0-9_.-]+$/, message: "Только латиница, цифры, _ . -" },
                })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
              />
              {errors.login && <p className="text-xs text-rose-600 mt-1">{errors.login.message}</p>}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Email</label>
              <input
                type="email" autoComplete="email"
                {...register("email", { required: "Введите email" })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
              />
              {errors.email && <p className="text-xs text-rose-600 mt-1">{errors.email.message}</p>}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Отображаемое имя</label>
              <input
                autoComplete="name"
                {...register("display_name", {
                  maxLength: { value: 128, message: "Максимум 128 символов" },
                })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
              />
              {errors.display_name && <p className="text-xs text-rose-600 mt-1">{errors.display_name.message}</p>}
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1.5">Пароль</label>
              <input
                type="password" autoComplete="new-password"
                {...register("password", {
                  required:  "Введите пароль",
                  minLength: { value: 6, message: "Минимум 6 символов" },
                })}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-600"
              />
              {errors.password && <p className="text-xs text-rose-600 mt-1">{errors.password.message}</p>}
            </div>

            {reg.isError && (
              <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded p-2.5">
                {extractErrorMessage(reg.error)}
              </div>
            )}

            <button
              type="submit"
              disabled={reg.isPending}
              className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium rounded"
            >
              {reg.isPending ? "Создаём…" : "Создать аккаунт"}
            </button>
          </form>

          <div className="mt-4 text-sm text-center text-slate-600">
            Уже есть аккаунт? <Link to="/login" className="text-blue-600 hover:underline">Войдите</Link>
          </div>
        </div>

      </div>
    </div>
  );
}
