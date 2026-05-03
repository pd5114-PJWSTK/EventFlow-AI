import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { DashboardPage } from "../pages/DashboardPage";
import { DataPage } from "../pages/DataPage";
import { IntakePage } from "../pages/IntakePage";
import { LoginPage } from "../pages/LoginPage";
import { MePage } from "../pages/MePage";
import { PlannerPage } from "../pages/PlannerPage";
import { PostEventPage } from "../pages/PostEventPage";
import { RuntimePage } from "../pages/RuntimePage";
import { UsersPage } from "../pages/UsersPage";

export function AppRoutes(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/new-event" element={<IntakePage />} />
          <Route path="/planning" element={<PlannerPage />} />
          <Route path="/replanning" element={<RuntimePage />} />
          <Route path="/post-event" element={<PostEventPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/me" element={<MePage />} />
          <Route path="/intake" element={<Navigate to="/new-event" replace />} />
          <Route path="/planner" element={<Navigate to="/planning" replace />} />
          <Route path="/runtime" element={<Navigate to="/replanning" replace />} />
          <Route path="/events" element={<Navigate to="/data" replace />} />
          <Route path="/resources" element={<Navigate to="/data" replace />} />
          <Route path="/ai" element={<Navigate to="/dashboard" replace />} />
          <Route path="/ml" element={<Navigate to="/me" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
