import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { LoginPage } from "../pages/LoginPage";

const loginMock = vi.fn();

vi.mock("../lib/auth", () => ({
  useAuth: () => ({
    login: loginMock,
  }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    loginMock.mockReset();
    loginMock.mockResolvedValue(undefined);
  });

  it("calls login on submit", async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Nazwa u¿ytkownika"), { target: { value: "user" } });
    fireEvent.change(screen.getByLabelText("Has³o"), { target: { value: "pass" } });
    fireEvent.click(screen.getByRole("button", { name: "Zaloguj" }));

    expect(loginMock).toHaveBeenCalledWith("user", "pass");
  });
});