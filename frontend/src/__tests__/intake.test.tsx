import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { IntakePage } from "../pages/IntakePage";

const requestMock = vi.fn();
const apiMock = {
  request: requestMock,
};

vi.mock("../lib/useAuth", () => ({
  useAuth: () => ({
    api: apiMock,
  }),
}));

describe("IntakePage", () => {
  beforeEach(() => {
    requestMock.mockReset();
    sessionStorage.clear();
  });

  it("fills business sheet from preview", async () => {
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/resources")) return Promise.resolve({ items: [], total: 0 });
      return Promise.resolve({
        draft: {
          event_name: "Executive Summit",
          client_name: "ACME",
          location_name: "Congress Centre",
          city: "Warsaw",
          event_type: "gala",
          attendee_count: 200,
          planned_start: "2026-06-12T10:00:00Z",
          planned_end: "2026-06-12T18:00:00Z",
          budget_estimate: 22000,
          event_priority: "medium",
          requirements: [{ requirement_type: "person_role", role_required: "coordinator", quantity: 2, mandatory: true }],
        },
        assumptions: [],
        parser_mode: "llm",
        used_fallback: false,
        gaps: [],
      });
    });

    render(<IntakePage />);

    fireEvent.click(screen.getByRole("button", { name: "Import" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith(
        "POST",
        "/api/ai-agents/ingest-event/preview",
        expect.objectContaining({ prefer_langgraph: true }),
      );
      expect(screen.getByDisplayValue("Executive Summit")).toBeInTheDocument();
      expect(screen.getByText("Source: LLM")).toBeInTheDocument();
      expect(screen.getByText("Requirements")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Add" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Check" }));
    expect(screen.getByRole("button", { name: "Add" })).not.toBeDisabled();
  });

  it("rejects numeric city before commit", async () => {
    requestMock.mockImplementation((_method: string, path: string) => {
      if (path.startsWith("/api/resources")) return Promise.resolve({ items: [], total: 0 });
      return Promise.resolve({
        draft: {
          event_name: "Executive Summit",
          client_name: "ACME",
          location_name: "Congress Centre",
          city: "12345",
          event_type: "gala",
          attendee_count: 200,
          planned_start: "2026-06-12T10:00:00Z",
          planned_end: "2026-06-12T18:00:00Z",
          budget_estimate: 22000,
          event_priority: "medium",
          requirements: [],
        },
        assumptions: [],
        parser_mode: "heuristic",
        used_fallback: true,
        gaps: [],
      });
    });

    render(<IntakePage />);

    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    await waitFor(() => expect(screen.getByDisplayValue("12345")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Check" }));

    expect(screen.getByText("City must contain letters, not only digits.")).toBeInTheDocument();
    expect(requestMock).not.toHaveBeenCalledWith("POST", "/api/ai-agents/ingest-event/commit", expect.anything());
  });
});
