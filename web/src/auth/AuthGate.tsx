import { Alert, Box, CircularProgress } from "@mui/material";
import { useEffect, useState, type ReactNode } from "react";

import { resolveUser } from "./signIn";

export interface AuthGateProps {
  children: ReactNode;
}

type AuthState = "loading" | "signed-in" | "failed";

export function AuthGate({ children }: AuthGateProps) {
  const [state, setState] = useState<AuthState>("loading");

  useEffect(() => {
    let active = true;
    resolveUser().then(
      (user) => active && user && setState("signed-in"),
      () => active && setState("failed"),
    );
    return () => {
      active = false;
    };
  }, []);

  if (state === "signed-in") {
    return children;
  }
  if (state === "failed") {
    return <Alert severity="error">Sign-in failed. Reload the page to try again.</Alert>;
  }
  return (
    <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
      <CircularProgress aria-label="Signing in" />
    </Box>
  );
}
