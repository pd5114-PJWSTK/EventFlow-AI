import { useEffect } from "react";
import { BrowserRouter } from "react-router-dom";
import { CssBaseline, ThemeProvider } from "@mui/material";

import { AuthProvider } from "../lib/auth";
import { useAuth } from "../lib/useAuth";
import { theme } from "./theme";
import { AppRoutes } from "./routes";

function Bootstrap(): JSX.Element {
  const { isAuthenticated, loadMe } = useAuth();

  useEffect(() => {
    if (isAuthenticated) {
      void loadMe();
    }
  }, [isAuthenticated, loadMe]);

  return <AppRoutes />;
}

export function App(): JSX.Element {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <AuthProvider>
          <Bootstrap />
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
