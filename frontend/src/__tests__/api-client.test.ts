import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClient } from "../lib/api";

describe("ApiClient hardening", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("maps network failures to a readable ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const client = new ApiClient(() => null, () => undefined);

    await expect(client.login("admin", "bad-pass")).rejects.toMatchObject({
      status: 0,
      message: "Brak polaczenia z API. Sprawdz, czy backend dziala i czy frontend ma poprawny adres API.",
    });
  });

  it("maps timeout to a readable ApiError", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: string, init?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      }),
    );

    const client = new ApiClient(() => null, () => undefined);
    const pending = client.login("admin", "secret");

    vi.advanceTimersByTime(15001);

    await expect(pending).rejects.toMatchObject({
      status: 0,
      message: "Przekroczono czas oczekiwania na odpowiedz API.",
    });
  });
});
