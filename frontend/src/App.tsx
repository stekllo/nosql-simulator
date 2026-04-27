import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout }                from "@/components/AppLayout";
import { BuilderCoursePage }        from "@/pages/BuilderCoursePage";
import { BuilderPage }              from "@/pages/BuilderPage";
import { CoursePage }               from "@/pages/CoursePage";
import { DashboardPage }            from "@/pages/DashboardPage";
import { HomePage }                 from "@/pages/HomePage";
import { LessonBuilderPage }        from "@/pages/LessonBuilderPage";
import { LessonPage }               from "@/pages/LessonPage";
import { LoginPage }                from "@/pages/LoginPage";
import { ProfilePage }              from "@/pages/ProfilePage";
import { RegisterPage }             from "@/pages/RegisterPage";
import { TaskBuilderPage }          from "@/pages/TaskBuilderPage";
import { TaskPage }                 from "@/pages/TaskPage";
import { TeacherStudentDetailPage } from "@/pages/TeacherStudentDetailPage";
import { TeacherStudentsPage }      from "@/pages/TeacherStudentsPage";
import { ProtectedRoute }           from "@/routes/ProtectedRoute";


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
        <Route path="/"                                  element={<HomePage          />} />
        <Route path="/courses/:courseId"                 element={<CoursePage        />} />
        <Route path="/lessons/:lessonId"                 element={<LessonPage        />} />
        <Route path="/tasks/:taskId"                     element={<TaskPage          />} />
        <Route path="/dashboard"                         element={<DashboardPage     />} />
        <Route path="/profile"                           element={<ProfilePage       />} />

        {/* Конструктор (backend сам проверяет роль teacher/admin через 403) */}
        <Route path="/builder"                           element={<BuilderPage       />} />
        <Route path="/builder/courses/:courseId"         element={<BuilderCoursePage />} />
        <Route path="/builder/modules/:moduleId/lessons/new"
                                                         element={<LessonBuilderPage />} />
        <Route path="/builder/lessons/:lessonId/edit"    element={<LessonBuilderPage />} />
        <Route path="/builder/lessons/:lessonId/tasks/new"
                                                         element={<TaskBuilderPage   />} />

        {/* Кабинет преподавателя (backend проверяет teacher/admin) */}
        <Route path="/teacher/students"                  element={<TeacherStudentsPage      />} />
        <Route path="/teacher/students/:userId"          element={<TeacherStudentDetailPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
