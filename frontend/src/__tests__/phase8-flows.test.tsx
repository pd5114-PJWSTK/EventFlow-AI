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

describe("Phase 8 operator flows", () => {
  beforeEach(() => {
    requestMock.mockReset();
    requestMock.mockResolvedValue({});
  });

  it("runs planner generate flow", async () => {
    render(<PlannerPage />);

    fireEvent.change(screen.getByLabelText("Event ID"), { target: { value: "event-123" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith("POST", "/api/planner/generate-plan", {
        event_id: "event-123",
        commit_to_assignments: true,
      });
    });
  });

  it("runs runtime parse and replan flow", async () => {
    requestMock.mockResolvedValueOnce({ parsed_incident: true }).mockResolvedValueOnce({ replanned: true });

    render(<RuntimePage />);

    fireEvent.change(screen.getByLabelText("Event ID"), { target: { value: "evt-live" } });
    fireEvent.click(screen.getByRole("button", { name: "Parse incydentu (LLM)" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenNthCalledWith(
        1,
        "POST",
        "/api/runtime/events/evt-live/incident/parse",
        expect.objectContaining({
          raw_log: expect.any(String),
          prefer_llm: true,
        }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Uruchom replan" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenNthCalledWith(
        2,
        "POST",
        "/api/planner/replan/evt-live",
        expect.objectContaining({
          incident_summary: expect.any(String),
          idempotency_key: expect.stringMatching(/^replan-/),
        }),
      );
    });
  });

  it("runs post-event parse and commit flow", async () => {
    requestMock
      .mockResolvedValueOnce({ draft_complete: { summary: "ok" } })
      .mockResolvedValueOnce({ outcome_saved: true });

    render(<PostEventPage />);

    fireEvent.change(screen.getByLabelText("Event ID"), { target: { value: "evt-post" } });
    fireEvent.click(screen.getByRole("button", { name: "Parse podsumowania" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenNthCalledWith(
        1,
        "POST",
        "/api/runtime/events/evt-post/post-event/parse",
        expect.objectContaining({
          raw_summary: expect.any(String),
          prefer_llm: true,
        }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /Zatwierd/ }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenNthCalledWith(
        2,
        "POST",
        "/api/runtime/events/evt-post/post-event/commit",
        expect.objectContaining({
          completion: expect.objectContaining({ summary: "ok" }),
          source_mode: "sheet_review",
        }),
      );
    });
  });
});
