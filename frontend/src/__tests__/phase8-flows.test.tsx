import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { PlannerPage } from "../pages/PlannerPage";
import { PostEventPage } from "../pages/PostEventPage";
import { RuntimePage } from "../pages/RuntimePage";

const requestMock = vi.fn();

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
      event_name: "Gala Testowa",
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
  items: [{ location_id: "loc-1", name: "Centrum", city: "Warszawa", location_type: "conference_center", parking_difficulty: 2, access_difficulty: 2, setup_complexity_score: 4 }],
  total: 1,
};

describe("Phase 8 CP-03 operator flows", () => {
  beforeEach(() => {
    requestMock.mockReset();
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
          selected_explanation: "Najniższy koszt przy pełnym pokryciu wymagań.",
          selected_plan: { event_id: "event-123", planner_run_id: "run", recommendation_id: "rec", plan_id: "plan", solver: "fallback", is_fully_assigned: true, assignments: [], estimated_cost: 10000 },
          candidates: [{ candidate_name: "balanced", solver: "fallback", estimated_cost: 10000, estimated_duration_minutes: 480, predicted_delay_risk: 0.1, coverage_ratio: 1, plan_score: 90, selection_explanation: "Najlepszy bilans kosztów i ryzyka." }],
        });
      }
      return Promise.resolve({ method, path, body });
    });

    render(<PlannerPage />);

    fireEvent.mouseDown(await screen.findByLabelText("Event do zaplanowania"));
    fireEvent.click(await screen.findByText(/Gala Testowa/));
    fireEvent.click(screen.getByRole("button", { name: "Zaplanuj" }));

    await waitFor(() => expect(screen.getByText("Najlepszy plan")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Wybierz" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("POST", "/api/planner/recommend-best-plan", expect.objectContaining({ commit_to_assignments: true }));
    });
  });

  it("runs runtime parse and replan decision flow", async () => {
    requestMock
      .mockResolvedValueOnce({ event_id: "evt-live", incident_id: "inc-1", incident_type: "equipment_failure", severity: "medium", description: "Awaria nagłośnienia", root_cause: "sprzęt", sla_impact: false, cost_impact: null, reported_by: "Jan", parser_mode: "llm", parse_confidence: 0.9 })
      .mockResolvedValueOnce({ event_id: "evt-live", comparison: { new_cost: 12000, cost_delta: 500, decision_note: "Zalecana wymiana sprzętu." }, generated_plan: { event_id: "evt-live", planner_run_id: "run", recommendation_id: "rec", plan_id: "plan", solver: "fallback", is_fully_assigned: true, assignments: [], estimated_cost: 12000 } });

    render(<RuntimePage />);

    fireEvent.change(screen.getByLabelText("Event ID"), { target: { value: "evt-live" } });
    fireEvent.click(screen.getByRole("button", { name: "Wprowadź" }));

    await waitFor(() => expect(screen.getByText("Arkusz incydentu")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Przyjmij zgłoszenie" }));

    await waitFor(() => expect(screen.getByText("Rekomendacja replanu")).toBeInTheDocument());
  });

  it("runs post-event parse and commit flow", async () => {
    requestMock
      .mockResolvedValueOnce({ event_id: "evt-post", parser_mode: "llm", parse_confidence: 0.9, gaps: [], draft_complete: { completed_at: "2026-06-12T18:00:00Z", total_delay_minutes: 0, actual_cost: 22000, sla_breached: false, summary_notes: "Wszystko zakończone poprawnie." } })
      .mockResolvedValueOnce({ committed_at: "2026-06-12T18:05:00Z" });

    render(<PostEventPage />);

    fireEvent.change(screen.getByLabelText("Event ID"), { target: { value: "evt-post" } });
    fireEvent.click(screen.getByRole("button", { name: "Wprowadź" }));

    await waitFor(() => expect(screen.getByText("Arkusz podsumowania")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Wprowadź" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("POST", "/api/runtime/events/evt-post/post-event/commit", expect.objectContaining({ source_mode: "sheet_review" }));
    });
  });
});
