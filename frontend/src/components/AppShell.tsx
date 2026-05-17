import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";
import {
  AppBar,
  Box,
  Button,
  Chip,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";

import { navItems } from "../app/navigation";
import { useAuth } from "../lib/useAuth";

const drawerWidth = 286;

export function AppShell(): JSX.Element {
  const { me, logout } = useAuth();
  const location = useLocation();

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{
          width: { xs: "100%", md: `calc(100% - ${drawerWidth}px)` },
          ml: { xs: 0, md: `${drawerWidth}px` },
          borderBottom: "1px solid",
          borderColor: "divider",
        }}
      >
        <Toolbar sx={{ justifyContent: "space-between", gap: 2 }}>
          <Typography variant="h6">EventFlow AI</Typography>
          <Stack direction="row" spacing={1} alignItems="center">
            {me?.roles?.slice(0, 3).map((role) => (
              <Chip key={role} label={role} size="small" color="primary" variant="outlined" />
            ))}
            <Button variant="contained" onClick={() => void logout()}>
              Log out
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
          display: { xs: "none", md: "block" },
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
                borderRadius: 1,
                mb: 0.5,
                color: "#ffffff",
                "&.Mui-selected": { backgroundColor: "rgba(255,255,255,0.2)" },
                "&.Mui-selected:hover": { backgroundColor: "rgba(255,255,255,0.26)" },
              }}
            >
              <ListItemIcon sx={{ color: "inherit", minWidth: 38 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} primaryTypographyProps={{ fontWeight: 700 }} />
            </ListItemButton>
          ))}
        </List>
      </Drawer>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: { xs: 2, md: 3 },
          mt: 9,
          maxWidth: "100%",
          minWidth: 0,
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
}
