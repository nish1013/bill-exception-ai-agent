import { ApolloError, type ServerError } from "@apollo/client";
import { describe, expect, it } from "vitest";

import { errorMessage } from "./errorMessage";

function httpError(status: number, result: unknown): ApolloError {
  const networkError = Object.assign(new Error(`HTTP ${status}`), {
    name: "ServerError",
    response: new Response(null, { status }),
    statusCode: status,
    result,
  }) as ServerError;
  return new ApolloError({ networkError });
}

describe("errorMessage", () => {
  it("us10: an HTTP 429 shows the quota message of its body", () => {
    const error = httpError(429, {
      errors: [{ message: "the tenant used 50 of 50 today", extensions: { code: "RATE_LIMITED" } }],
    });

    expect(errorMessage(error)).toBe(
      "Too many requests. Wait and try again. the tenant used 50 of 50 today",
    );
  });

  it("us10: a network error with no body shows that the API is not reachable", () => {
    expect(errorMessage(new ApolloError({ networkError: new TypeError("fetch failed") }))).toBe(
      "The API is not reachable.",
    );
  });

  it("us10: a GraphQL error with a code shows its message", () => {
    const error = new ApolloError({
      graphQLErrors: [{ message: "exception not found", extensions: { code: "NOT_FOUND" } }],
    });

    expect(errorMessage(error)).toBe("Not found. exception not found");
  });
});
