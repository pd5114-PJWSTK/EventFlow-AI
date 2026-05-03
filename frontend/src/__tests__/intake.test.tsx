import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { IntakePage } from "../pages/IntakePage";

const requestMock = vi.fn();

vi.mock("../lib/auth", () => ({
  useAuth: () => ({
    api: {
      request: requestMock,
    },
  }),
}));

describe("IntakePage", () => {
  beforeEach(() => {
    requestMock.mockReset();
  });

  it("fills business sheet from preview", async () => {
    requestMock.mockResolvedValueOnce({
      draft: {
        event_name: "Gala Testowa",
        client_name: "ACME",
        location_name: "Centrum Kongresowe",
        city: "Warszawa",
        event_type: "gala",
        attendee_count: 200,
        planned_start: "2026-06-12T10:00:00Z",
        planned_end: "2026-06-12T18:00:00Z",
        budget_estimate: 22000,
        event_priority: "medium",
        requirements: [],
      },
      assumptions: [],
      parser_mode: "hybrid_llm",
      used_fallback: false,
      gaps: [],
    });

    render(<IntakePage />);

    fireEvent.click(screen.getByRole("button", { name: "Wprowadź" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith(
        "POST",
        "/api/ai-agents/ingest-event/preview",
        expect.objectContaining({ prefer_langgraph: true }),
      );
      expect(screen.getByDisplayValue("Gala Testowa")).toBeInTheDocument();
      expect(screen.getByText("Źródło: LLM")).toBeInTheDocument();
    });
  });
});
