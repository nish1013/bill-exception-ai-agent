import { ApolloError } from "@apollo/client";

interface ApiError {
  message?: string;
  extensions?: { code?: unknown };
}

interface ErrorBody {
  errors?: ApiError[];
}

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
    const first = error.graphQLErrors[0] ?? bodyError(error.networkError);
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

// A 401 or 429 arrives as an HTTP error, so Apollo puts its GraphQL body on the network error.
function bodyError(networkError: unknown): ApiError | undefined {
  if (networkError && typeof networkError === "object" && "result" in networkError) {
    const body = networkError.result as ErrorBody | undefined;
    return body?.errors?.[0];
  }
  return undefined;
}
