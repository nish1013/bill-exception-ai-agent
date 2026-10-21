import { useMemo } from "react";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router";

import { BillsPage } from "./bills/BillsPage";
import { InboxPage } from "./inbox/InboxPage";
import { AppShell } from "./layout/AppShell";
import { ProposalPage } from "./proposals/ProposalPage";
import { ProposalsPage } from "./proposals/ProposalsPage";

export function App() {
  // Created after sign-in, so the router starts at the path that the callback restored.
  const router = useMemo(
    () =>
      createBrowserRouter([
        {
          path: "/",
          element: <AppShell />,
          children: [
            { index: true, element: <Navigate to="/bills" replace /> },
            { path: "bills", element: <BillsPage /> },
            { path: "inbox", element: <InboxPage /> },
            { path: "proposals", element: <ProposalsPage /> },
            { path: "proposals/:proposalId", element: <ProposalPage /> },
            { path: "*", element: <Navigate to="/bills" replace /> },
          ],
        },
      ]),
    [],
  );
  return <RouterProvider router={router} />;
}
