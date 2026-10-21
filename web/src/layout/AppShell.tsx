import { useQuery } from "@apollo/client";
import { AppBar, Box, Button, Container, Tab, Tabs, Toolbar, Typography } from "@mui/material";
import { Link, Outlet, useLocation } from "react-router";

import { signOut } from "../auth/signIn";
import { VIEWER } from "../graphql/operations";

interface NavTab {
  path: string;
  label: string;
}

const TABS: NavTab[] = [
  { path: "/bills", label: "Bills" },
  { path: "/inbox", label: "Inbox" },
];

export function AppShell() {
  const { pathname } = useLocation();
  const { data } = useQuery(VIEWER);
  const current = TABS.find((tab) => pathname.startsWith(tab.path))?.path ?? false;

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="static">
        <Toolbar sx={{ gap: 2 }}>
          <Typography variant="h6" component="span" sx={{ flexGrow: 1 }}>
            Bill exceptions
          </Typography>
          {data && (
            <Typography variant="body2" aria-label="Signed in as">
              {data.viewer.tenantName} · {data.viewer.role}
            </Typography>
          )}
          <Button color="inherit" onClick={() => void signOut()}>
            Sign out
          </Button>
        </Toolbar>
        <Tabs value={current} textColor="inherit" indicatorColor="secondary" sx={{ px: 2 }}>
          {TABS.map((tab) => (
            <Tab key={tab.path} value={tab.path} label={tab.label} component={Link} to={tab.path} />
          ))}
        </Tabs>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 3 }}>
        <Outlet />
      </Container>
    </Box>
  );
}
