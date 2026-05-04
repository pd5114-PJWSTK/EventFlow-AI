import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";

import { AppShell } from "../components/AppShell";
import { DashboardPage } from "../pages/DashboardPage";
import { DataPage } from "../pages/DataPage";
import { MePage } from "../pages/MePage";
import { UsersPage } from "../pages/UsersPage";

const requestMock = vi.fn();

vi.mock("../lib/auth", () => ({
  useAuth: () => ({
    me: { username: "admin", roles: ["admin", "manager"], is_superadmin: true },
    logout: vi.fn(),
    api: { request: requestMock, logoutAll: vi.fn() },
  }),
}));

const eventList = {
  items: [
    {
      event_id: "event-1",
      client_id: "client-1",
      location_id: "loc-1",
      event_name: "Poland Conference",
      event_type: "conference",
      planned_start: "2026-06-12T10:00:00Z",
      planned_end: "2026-06-12T18:00:00Z",
      priority: "medium",
      status: "draft",
      budget_estimate: 10000,
    },
  ],
  total: 1,
};

const locationList = {
  items: [{ location_id: "loc-1", name: "Congress Centre", city: "Warsaw", location_type: "conference_center", parking_difficulty: 2, access_difficulty: 2, setup_complexity_score: 4 }],
  total: 1,
};

describe("CP-05 business UI", () => {
  beforeEach(() => {
    requestMock.mockReset();
    sessionStorage.clear();
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/events")) return Promise.resolve(eventList);
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path.startsWith("/api/resources/people")) return Promise.resolve({ items: [], total: 0 });
      if (path.startsWith("/api/resources/equipment-types")) return Promise.resolve({ items: [], total: 0 });
      if (path.startsWith("/api/resources/equipment")) return Promise.resolve({ items: [], total: 0 });
      if (path.startsWith("/api/resources/vehicles")) return Promise.resolve({ items: [], total: 0 });
      if (path.startsWith("/api/resources/skills")) return Promise.resolve({ items: [], total: 0 });
      if (path.startsWith("/admin/users")) return Promise.resolve({ items: [{ user_id: "u1", username: "admin", roles: ["admin"], is_active: true, is_superadmin: true }], total: 1 });
      if (path.startsWith("/auth/me")) return Promise.resolve({ user_id: "u1", username: "admin", roles: ["admin"], is_superadmin: true });
      if (path.startsWith("/api/ml/models")) return Promise.resolve({ items: [], total: 0 });
      if (path.startsWith("/api/ai-agents/llm-status")) return Promise.resolve({ enabled: false, configured: false, endpoint_configured: false, api_key_configured: false, deployment_configured: false, mode: "fallback", message: "LLM disabled." });
      return Promise.resolve({});
    });
  });

  it("renders the required sidebar labels", () => {
    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<div />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    for (const label of ["Dashboard", "New event", "Event planning", "Live replanning", "Post-event log", "Data", "Users", "My account"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders dashboard descriptions and upcoming events with English text", async () => {
    render(<DashboardPage />);

    expect(screen.getByText("Console modules")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Poland Conference")).toBeInTheDocument());
    expect(screen.getByText(/Upcoming events/)).toBeInTheDocument();
  });

  it("renders read-only business data tables", async () => {
    render(<DataPage />);

    await waitFor(() => expect(screen.getByText("Poland Conference")).toBeInTheDocument());
    expect(screen.getByText("Budget")).toBeInTheDocument();
  });

  it("renders users as a form and table", async () => {
    render(<UsersPage />);

    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("User list")).toBeInTheDocument());
  });

  it("renders account details and admin model tab", async () => {
    render(<MePage />);

    await waitFor(() => expect(screen.getByText("User")).toBeInTheDocument());
    expect(screen.getByText("ML model")).toBeInTheDocument();
  });
});
