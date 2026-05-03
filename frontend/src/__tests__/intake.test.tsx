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

  it("fills draft from preview", async () => {
    requestMock.mockResolvedValueOnce({
      draft: { event_name: "Sample", requirements: [] },
      assumptions: [],
      parser_mode: "hybrid_llm",
      used_fallback: false,
      gaps: [],
    });

    render(<IntakePage />);

    fireEvent.click(screen.getByRole("button", { name: "Preview parse" }));

    await waitFor(() => {
      expect(requestMock).toHaveBeenCalledWith(
        "POST",
        "/api/ai-agents/ingest-event/preview",
        expect.any(Object),
      );
      expect(screen.getByDisplayValue(/Sample/)).toBeInTheDocument();
    });
  });
});