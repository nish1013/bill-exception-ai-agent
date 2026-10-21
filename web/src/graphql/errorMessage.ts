import { ApolloError } from "@apollo/client";

const MESSAGES: Record<string, string> = {
  VALIDATION: "The API refused a value.",
  FORBIDDEN: "Your role cannot do this.",
  NOT_FOUND: "Not found.",
  CONFLICT: "This conflicts with the current data.",
  IDEMPOTENCY_MISMATCH: "This bill was already sent with other values.",
  RATE_LIMITED: "Too many requests. Wait and try again.",
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApolloError) {
    const first = error.graphQLErrors[0];
    const code = first?.extensions?.code;
    if (typeof code === "string" && code in MESSAGES) {
      return `${MESSAGES[code]} ${first?.message ?? ""}`.trim();
    }
    if (error.networkError) {
      return "The API is not reachable.";
    }
  }
  return "Something went wrong.";
}
