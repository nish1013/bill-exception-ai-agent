import { ApolloClient, HttpLink, InMemoryCache, from } from "@apollo/client";
import { setContext } from "@apollo/client/link/context";
import { onError } from "@apollo/client/link/error";

import { signInAgain } from "../auth/signIn";
import { userManager } from "../auth/userManager";

const UNAUTHORIZED = 401;

const authLink = setContext(async (_, previous) => {
  const user = await userManager.getUser();
  if (!user) {
    return previous;
  }
  return { headers: { ...previous.headers, Authorization: `Bearer ${user.access_token}` } };
});

const signInOnUnauthorized = onError(({ networkError }) => {
  if (networkError && "statusCode" in networkError && networkError.statusCode === UNAUTHORIZED) {
    void signInAgain();
  }
});

export const apolloClient = new ApolloClient({
  link: from([signInOnUnauthorized, authLink, new HttpLink({ uri: "/graphql" })]),
  cache: new InMemoryCache({ typePolicies: { Viewer: { keyFields: [] } } }),
});
