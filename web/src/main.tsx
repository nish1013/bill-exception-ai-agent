import { ApolloProvider } from "@apollo/client";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { AuthGate } from "./auth/AuthGate";
import { apolloClient } from "./graphql/client";
import { theme } from "./theme";

const root = document.getElementById("root");
if (!root) {
  throw new Error("index.html has no #root element");
}

createRoot(root).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthGate>
        <ApolloProvider client={apolloClient}>
          <App />
        </ApolloProvider>
      </AuthGate>
    </ThemeProvider>
  </StrictMode>,
);
