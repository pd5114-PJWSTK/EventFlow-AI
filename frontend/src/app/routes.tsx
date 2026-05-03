import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { AIAgentsPage } from "../pages/AIAgentsPage";
import { DashboardPage } from "../pages/DashboardPage";
import { EventsPage } from "../pages/EventsPage";
import { IntakePage } from "../pages/IntakePage";
import { LoginPage } from "../pages/LoginPage";
import { MePage } from "../pages/MePage";
import { MLPage } from "../pages/MLPage";
import { PlannerPage } from "../pages/PlannerPage";
import { PostEventPage } from "../pages/PostEventPage";
import { ResourcesPage } from "../pages/ResourcesPage";
import { RuntimePage } from "../pages/RuntimePage";
import { UsersPage } from "../pages/UsersPage";

export function AppRoutes(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/intake" element={<IntakePage />} />
          <Route path="/planner" element={<PlannerPage />} />
          <Route path="/runtime" element={<RuntimePage />} />
          <Route path="/post-event" element={<PostEventPage />} />
          <Route path="/events" element={<EventsPage />} />
          <Route path="/resources" element={<ResourcesPage />} />
          <Route path="/ai" element={<AIAgentsPage />} />
          <Route path="/ml" element={<MLPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/me" element={<MePage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}