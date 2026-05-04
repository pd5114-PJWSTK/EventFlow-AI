import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { PlannerPage } from "../pages/PlannerPage";
import { PostEventPage } from "../pages/PostEventPage";
import { RuntimePage } from "../pages/RuntimePage";

const requestMock = vi.fn();

vi.mock("../components/EventSelect", () => ({
  EventSelect: ({ label, value, onChange }: { label: string; value: string; onChange: (eventId: string) => void }) => (
    <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">Select event</option>
      <option value="event-123">Executive Summit</option>
      <option value="evt-live">Executive Summit live</option>
      <option value="evt-post">Executive Summit post</option>
    </select>
  ),
}));
vi.mock("../lib/auth", () => ({
  useAuth: () => ({
    api: {
      request: requestMock,
    },
  }),
}));

const eventList = {
  items: [
    {
      event_id: "event-123",
      client_id: "client-1",
      location_id: "loc-1",
      event_name: "Executive Summit",
      event_type: "gala",
      planned_start: "2026-06-12T10:00:00Z",
      planned_end: "2026-06-12T18:00:00Z",
      priority: "medium",
      status: "draft",
    },
  ],
  total: 1,
};

const locationList = {
  items: [{ location_id: "loc-1", name: "Congress Centre", city: "Warsaw", location_type: "conference_center", parking_difficulty: 2, access_difficulty: 2, setup_complexity_score: 4 }],
  total: 1,
};

describe("Phase 8 CP-05 operator flows", () => {
  beforeEach(() => {
    requestMock.mockReset();
    sessionStorage.clear();
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/events")) return Promise.resolve(eventList);
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      return Promise.resolve({});
    });
  });

  it("runs planning flow with business labels", async () => {
    requestMock.mockImplementation((method: string, path: string, body?: unknown) => {
      if (path.startsWith("/api/events")) return Promise.resolve(eventList);
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path === "/api/planner/generate-plan") {
        return Promise.resolve({ event_id: "event-123", planner_run_id: "run", recommendation_id: "rec", plan_id: "plan", solver: "fallback", is_fully_assigned: true, assignments: [], estimated_cost: 10000 });
      }
      if (path === "/api/planner/recommend-best-plan") {
        return Promise.resolve({
          event_id: "event-123",
          selected_candidate_name: "balanced",
          selected_explanation: "Lowest cost with full requirement coverage.",
          selected_plan: { event_id: "event-123", planner_run_id: "run", recommendation_id: "rec", plan_id: "plan", solver: "fallback", is_fully_assigned: true, assignments: [], estimated_cost: 10000 },
          candidates: [{ candidate_name: "balanced", solver: "fallback", estimated_cost: 10000, estimated_duration_minutes: 480, predicted_delay_risk: 0.1, coverage_ratio: 1, plan_score: 90, selection_explanation: "Best cost and risk balance." }],
        });
      }
      return Promise.resolve({ method, path, body });
    });

    render(<PlannerPage />);

    fireEvent.change(await screen.findByLabelText("Event to plan"), { target: { value: "event-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan event" }));

    await waitFor(() => expect(screen.getByText("Recommended plan")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Select plan" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("POST", "/api/planner/recommend-best-plan", expect.objectContaining({ commit_to_assignments: true }));
    });
  });

  it("runs runtime parse and replan decision flow", async () => {
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/events")) return Promise.resolve({ ...eventList, items: [{ ...eventList.items[0], event_id: "evt-live", status: "planned" }] });
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path === "/api/runtime/events/evt-live/incident/parse") {
        return Promise.resolve({ event_id: "evt-live", incident_id: "inc-1", incident_type: "equipment_failure", severity: "medium", description: "Sound system failure", root_cause: "equipment", sla_impact: false, cost_impact: null, reported_by: "Jane", parser_mode: "llm", parse_confidence: 0.9 });
      }
      if (path === "/api/planner/replan/evt-live") {
        return Promise.resolve({ event_id: "evt-live", comparison: { new_cost: 12000, cost_delta: 500, decision_note: "Recommended equipment replacement." }, generated_plan: { event_id: "evt-live", planner_run_id: "run", recommendation_id: "rec", plan_id: "plan", solver: "fallback", is_fully_assigned: true, assignments: [], estimated_cost: 12000 } });
      }
      return Promise.resolve({});
    });

    render(<RuntimePage />);

    fireEvent.change(await screen.findByLabelText("Event for incident"), { target: { value: "evt-live" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(screen.getByText("Incident sheet")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Accept incident" }));

    await waitFor(() => expect(screen.getByText("Replan recommendation")).toBeInTheDocument());
  });

  it("runs post-event parse and commit flow", async () => {
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/events")) return Promise.resolve({ ...eventList, items: [{ ...eventList.items[0], event_id: "evt-post", status: "planned" }] });
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path === "/api/runtime/events/evt-post/post-event/parse") {
        return Promise.resolve({ event_id: "evt-post", parser_mode: "llm", parse_confidence: 0.9, gaps: [], draft_complete: { completed_at: "2026-06-12T18:00:00Z", total_delay_minutes: 0, actual_cost: 22000, sla_breached: false, summary_notes: "Everything completed correctly." } });
      }
      if (path === "/api/runtime/events/evt-post/post-event/commit") return Promise.resolve({ committed_at: "2026-06-12T18:05:00Z" });
      return Promise.resolve({});
    });

    render(<PostEventPage />);

    fireEvent.change(await screen.findByLabelText("Event to close"), { target: { value: "evt-post" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(screen.getByText("Completion sheet")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("POST", "/api/runtime/events/evt-post/post-event/commit", expect.objectContaining({ source_mode: "sheet_review" }));
    });
  });
});
