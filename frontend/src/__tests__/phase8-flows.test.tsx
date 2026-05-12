import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { PlannerPage } from "../pages/PlannerPage";
import { PostEventPage } from "../pages/PostEventPage";
import { RuntimePage } from "../pages/RuntimePage";

const requestMock = vi.fn();
const apiMock = {
  request: requestMock,
};

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
vi.mock("../components/EventDetailsCard", () => ({
  EventDetailsCard: ({ title }: { title: string }) => <div>{title}</div>,
}));
vi.mock("../lib/useAuth", () => ({
  useAuth: () => ({
    api: apiMock,
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
const peopleList = {
  items: [{ person_id: "person-audio", full_name: "Audio Technician", role: "technician_audio", active: true, availability_status: "available", cost_per_hour: 90 }],
  total: 1,
};
const equipmentTypeList = {
  items: [{ equipment_type_id: "type-audio", type_name: "Audio kit" }],
  total: 1,
};
const equipmentList = {
  items: [{ equipment_id: "eq-audio", equipment_type_id: "type-audio", asset_tag: "Audio replacement kit", active: true, status: "available", hourly_cost_estimate: 120 }],
  total: 1,
};
const vehicleList = {
  items: [{ vehicle_id: "van-1", vehicle_name: "Service van", vehicle_type: "van", active: true, status: "available", cost_per_hour: 80 }],
  total: 1,
};
const emptyList = { items: [], total: 0 };

describe("Phase 8 CP-07 operator flows", () => {
  beforeEach(() => {
    requestMock.mockReset();
    sessionStorage.clear();
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/events")) return Promise.resolve(eventList);
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path.startsWith("/api/resources/people")) return Promise.resolve(peopleList);
      if (path.startsWith("/api/resources/equipment-types")) return Promise.resolve(equipmentTypeList);
      if (path.startsWith("/api/resources/equipment")) return Promise.resolve(equipmentList);
      if (path.startsWith("/api/resources/vehicles")) return Promise.resolve(vehicleList);
      if (path.startsWith("/api/resources/skills")) return Promise.resolve(emptyList);
      return Promise.resolve(emptyList);
    });
  });

  it("runs planning flow with business labels", async () => {
    requestMock.mockImplementation((method: string, path: string, body?: unknown) => {
      if (path.startsWith("/api/events")) return Promise.resolve(eventList);
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path.includes("/requirements")) return Promise.resolve({ items: [{ requirement_id: "req-1", requirement_type: "person_role", role_required: "coordinator", quantity: 1 }], total: 1 });
      if (path.includes("/assignments")) return Promise.resolve(emptyList);
      if (path.startsWith("/api/resources/people")) return Promise.resolve(peopleList);
      if (path.startsWith("/api/resources/equipment-types")) return Promise.resolve(equipmentTypeList);
      if (path.startsWith("/api/resources/equipment")) return Promise.resolve(equipmentList);
      if (path.startsWith("/api/resources/vehicles")) return Promise.resolve(vehicleList);
      if (path.startsWith("/api/resources/skills")) return Promise.resolve(emptyList);
      if (path === "/api/planner/generate-plan") {
        return Promise.resolve({
          event_id: "event-123",
          planner_run_id: "run",
          recommendation_id: "rec",
          plan_id: "plan",
          solver: "fallback",
          is_fully_assigned: true,
          assignments: [{ requirement_id: "req-1", resource_type: "person", resource_ids: ["person-audio"], unassigned_count: 0, estimated_cost: 720 }],
          estimated_cost: 10000,
          stage_breakdown: [{ stage_key: "outbound_transport", label: "Outbound transport", duration_minutes: 45, description: "Crew arrives at venue.", drivers: ["Close team base"] }],
        });
      }
      if (path === "/api/planner/recommend-best-plan") {
        return Promise.resolve({
          event_id: "event-123",
          selected_candidate_name: "balanced",
          selected_explanation: "Lowest cost with full requirement coverage.",
          business_explanation: {
            source: "deterministic",
            summary: "Optimized plan uses a closer and more reliable team.",
            baseline_vs_optimized: "Delay risk is lower because travel is shorter.",
            drivers: ["Closer current location", "Higher reliability"],
            metric_explanations: [{ metric_key: "predicted_delay_risk", label: "Delay risk", summary: "Risk of late delivery.", drivers: ["travel time"], delta_direction: "better" }],
            resource_impact_summary: [{ resource_id: "person-audio", resource_name: "Audio Technician", resource_type: "person", summary: "Close to venue.", distance_to_event_km: 4.2, travel_time_minutes: 12, logistics_cost: 20, contribution: "Fast arrival" }],
          },
          selected_plan: {
            event_id: "event-123",
            planner_run_id: "run",
            recommendation_id: "rec",
            plan_id: "plan",
            solver: "fallback",
            is_fully_assigned: true,
            assignments: [{ requirement_id: "req-1", resource_type: "person", resource_ids: ["person-audio"], unassigned_count: 0, estimated_cost: 720 }],
            estimated_cost: 10000,
            stage_breakdown: [{ stage_key: "outbound_transport", label: "Outbound transport", duration_minutes: 30, description: "Crew arrives from nearby base.", drivers: ["Short travel"] }],
            assignment_slots: [{
              requirement_id: "req-1",
              slot_index: 1,
              resource_type: "person",
              business_label: "Coordinator 1",
              selected_resource_id: "person-audio",
              selected_resource_name: "Audio Technician",
              estimated_cost: 720,
              candidate_options: [{ resource_id: "person-audio", resource_name: "Audio Technician", recommendation_score: 92, estimated_cost: 720, distance_to_event_km: 4.2, travel_time_minutes: 12, logistics_cost: 20, location_match_score: 0.98, location_note: "Close to venue.", availability_note: "Available.", why_recommended: "Strong reliability and short travel." }],
            }],
          },
          candidates: [
            { candidate_name: "balanced", solver: "fallback", estimated_cost: 10000, estimated_duration_minutes: 480, predicted_delay_risk: 0.1, coverage_ratio: 1, plan_score: 90, selection_explanation: "Best cost and risk balance." },
            { candidate_name: "cost_guarded", solver: "fallback", estimated_cost: 9000, estimated_duration_minutes: 510, predicted_delay_risk: 0.15, coverage_ratio: 0.95, plan_score: 84, selection_explanation: "Lower cost with a little more risk." },
          ],
        });
      }
      return Promise.resolve({ method, path, body });
    });

    render(<PlannerPage />);

    fireEvent.change(await screen.findByLabelText("Event to plan"), { target: { value: "event-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan event" }));

    await waitFor(() => expect(screen.getByText("Optimized plan")).toBeInTheDocument());
    expect(screen.getByText("Why optimized is different")).toBeInTheDocument();
    expect(screen.getByText("Timeline")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next: review resources" }));
    await waitFor(() => expect(screen.getByText("Review resource assignments before final approval")).toBeInTheDocument());
    expect(screen.getByText(/Close to venue/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve final plan" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("POST", "/api/planner/recommend-best-plan", expect.objectContaining({ commit_to_assignments: true }));
    });
  });

  it("runs runtime parse and replan decision flow", async () => {
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/events")) return Promise.resolve({ ...eventList, items: [{ ...eventList.items[0], event_id: "evt-live", status: "planned" }] });
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path.startsWith("/api/resources/people")) return Promise.resolve(peopleList);
      if (path.startsWith("/api/resources/equipment-types")) return Promise.resolve(equipmentTypeList);
      if (path.startsWith("/api/resources/equipment")) return Promise.resolve(equipmentList);
      if (path.startsWith("/api/resources/vehicles")) return Promise.resolve(vehicleList);
      if (path === "/api/runtime/events/evt-live/incident/parse") {
        return Promise.resolve({ event_id: "evt-live", incident_id: "inc-1", incident_type: "equipment_failure", severity: "medium", description: "Sound system failure", root_cause: "equipment", sla_impact: false, cost_impact: null, reported_by: "Jane", parser_mode: "llm", parse_confidence: 0.9 });
      }
      if (path === "/api/planner/replan/evt-live") {
        return Promise.resolve({ event_id: "evt-live", comparison: { new_cost: 12000, cost_delta: 500, decision_note: "Recommended equipment replacement." }, generated_plan: { event_id: "evt-live", planner_run_id: "run", recommendation_id: "rec", plan_id: "plan", solver: "fallback", is_fully_assigned: true, assignments: [{ requirement_id: "req-audio", resource_type: "equipment", resource_ids: ["eq-audio"], unassigned_count: 0, estimated_cost: 960 }], estimated_cost: 12000 } });
      }
      return Promise.resolve(emptyList);
    });

    render(<RuntimePage />);

    fireEvent.change(await screen.findByLabelText("Event for incident"), { target: { value: "evt-live" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(screen.getByText("Incident sheet")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    fireEvent.click(screen.getByRole("button", { name: "Accept incident" }));

    await waitFor(() => expect(screen.getByText("Replan recommendation")).toBeInTheDocument());
    expect(screen.getByDisplayValue(/replacement audio equipment/i)).toBeInTheDocument();
  });

  it("runs post-event parse and commit flow", async () => {
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/events")) return Promise.resolve({ ...eventList, items: [{ ...eventList.items[0], event_id: "evt-post", status: "completed" }] });
      if (path.startsWith("/api/locations")) return Promise.resolve(locationList);
      if (path === "/api/runtime/events/evt-post/post-event/parse") {
        return Promise.resolve({ event_id: "evt-post", parser_mode: "llm", parse_confidence: 0.9, gaps: [], draft_complete: { completed_at: "2026-06-12T18:00:00Z", total_delay_minutes: 0, actual_cost: 22000, sla_breached: false, client_satisfaction_score: 4.8, internal_quality_score: 4.6, summary_notes: "Everything completed correctly." } });
      }
      if (path === "/api/runtime/events/evt-post/post-event/commit") return Promise.resolve({ committed_at: "2026-06-12T18:05:00Z" });
      return Promise.resolve({});
    });

    render(<PostEventPage />);

    fireEvent.change(await screen.findByLabelText("Completed event to log"), { target: { value: "evt-post" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => expect(screen.getByText("Completion sheet")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("POST", "/api/runtime/events/evt-post/post-event/commit", expect.objectContaining({ source_mode: "sheet_review" }));
    });
  });
});
