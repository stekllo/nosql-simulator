import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout }       from "@/components/AppLayout";
import { HomePage }        from "@/pages/HomePage";
import { LoginPage }       from "@/pages/LoginPage";
import { ProfilePage }     from "@/pages/ProfilePage";
import { RegisterPage }    from "@/pages/RegisterPage";
import { ProtectedRoute }  from "@/routes/ProtectedRoute";


export default function App() {
  return (
    <Routes>
      <Route path="/login"    element={<LoginPage    />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/"         element={<HomePage    />} />
        <Route path="/profile"  element={<ProfilePage />} />
        <Route path="/learning" element={<div className="max-w-5xl mx-auto px-6 py-10 text-sm text-slate-500">Раздел «Обучение» появится позже.</div>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
