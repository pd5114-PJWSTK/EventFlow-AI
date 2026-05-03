import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import {
  AppBar,
  Box,
  Button,
  Chip,
  Drawer,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";

import { useAuth } from "../lib/auth";

const navItems = [
  { label: "Dashboard", path: "/dashboard" },
  { label: "Intake AI", path: "/intake" },
  { label: "Planner Studio", path: "/planner" },
  { label: "Runtime + Replan", path: "/runtime" },
  { label: "Post-Event Log", path: "/post-event" },
  { label: "Eventy", path: "/events" },
  { label: "Zasoby", path: "/resources" },
  { label: "AI Agents", path: "/ai" },
  { label: "ML", path: "/ml" },
  { label: "U¿ytkownicy", path: "/users" },
  { label: "Moje konto", path: "/me" },
];

const drawerWidth = 270;

export function AppShell(): JSX.Element {
  const { me, logout } = useAuth();
  const location = useLocation();

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{ width: `calc(100% - ${drawerWidth}px)`, ml: `${drawerWidth}px`, borderBottom: "1px solid", borderColor: "divider" }}
      >
        <Toolbar sx={{ justifyContent: "space-between" }}>
          <Typography variant="h6">EventFlow AI Admin Console</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            {me?.roles?.slice(0, 3).map((role) => (
              <Chip key={role} label={role} size="small" color="primary" variant="outlined" />
            ))}
            <Button variant="contained" onClick={() => void logout()}>
              Wyloguj
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        anchor="left"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: drawerWidth,
            boxSizing: "border-box",
            background: "linear-gradient(180deg, #0f766e 0%, #115e59 80%)",
            color: "#fff",
          },
        }}
      >
        <Toolbar>
          <Typography variant="h5">Console</Typography>
        </Toolbar>
        <List sx={{ px: 1 }}>
          {navItems.map((item) => (
            <ListItemButton
              key={item.path}
              component={RouterLink}
              to={item.path}
              selected={location.pathname === item.path}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                color: "#ffffff",
                "&.Mui-selected": { backgroundColor: "rgba(255,255,255,0.2)" },
              }}
            >
              <ListItemText primary={item.label} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 9, ml: `${drawerWidth}px` }}>
        <Outlet />
      </Box>
    </Box>
  );
}