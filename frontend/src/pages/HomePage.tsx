/**
 * Стартовая страница: проверяет, что бэкенд жив, и показывает статус
 * каждой из 6 зависимостей (Postgres + 4 NoSQL + Redis-broker).
 *
 * Это служебная страница на время разработки — пока нет авторизации
 * и каталога курсов, она помогает понять, что окружение поднялось.
 */
import { useEffect, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface ServiceStatus {
  name:    string;
  status:  "ok" | "down";
  detail?: string | null;
}

interface HealthResponse {
  status:   "ok" | "degraded";
  services: ServiceStatus[];
}

export function HomePage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error,  setError]  = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchHealth = async () => {
      try {
        const res  = await fetch(`${API_URL}/health`);
        const data = (await res.json()) as HealthResponse;
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(String(err));
      }
    };

    fetchHealth();
    const id = setInterval(fetchHealth, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-2xl w-full">

        <header className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-md bg-blue-600 text-white flex items-center justify-center font-bold text-lg">
            N
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">NoSQL Simulator</h1>
            <p className="text-sm text-slate-500">Локальная среда разработки запущена</p>
          </div>
        </header>

        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">
            Статус сервисов
          </h2>

          {error && (
            <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-md p-3 mb-4">
              Не удалось получить данные с бэкенда: {error}
              <div className="text-xs text-rose-600 mt-1">
                Проверь, что контейнер <code>ns-backend</code> запущен и слушает
                на <code>http://localhost:8000</code>.
              </div>
            </div>
          )}

          {!health && !error && (
            <div className="text-sm text-slate-500">Загрузка…</div>
          )}

          {health && (
            <ul className="space-y-2">
              {health.services.map((svc) => (
                <li
                  key={svc.name}
                  className="flex items-center justify-between p-3 rounded-md bg-slate-50 border border-slate-100"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={
                        "w-2 h-2 rounded-full " +
                        (svc.status === "ok" ? "bg-emerald-500" : "bg-rose-500")
                      }
                    />
                    <span className="font-mono text-sm">{svc.name}</span>
                  </div>
                  <div className="text-xs">
                    {svc.status === "ok" ? (
                      <span className="text-emerald-700 font-medium">OK</span>
                    ) : (
                      <span className="text-rose-700" title={svc.detail ?? ""}>
                        DOWN
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <footer className="mt-6 text-xs text-slate-500 text-center">
          API: <a href={`${API_URL}/docs`} className="underline hover:text-blue-600">{API_URL}/docs</a>
        </footer>

      </div>
    </div>
  );
}
