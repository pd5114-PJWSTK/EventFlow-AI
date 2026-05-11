import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, Chip, Grid, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";

import { BusinessTable } from "../components/BusinessTable";
import { StatusBanner } from "../components/StatusBanner";
import { useAuth } from "../lib/useAuth";
import type { AdminUser, ListResponse } from "../types/api";

const roleOptions = ["admin", "manager", "coordinator", "technician"];

export function UsersPage(): JSX.Element {
  const { api } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [username, setUsername] = useState("operator-ui");
  const [password, setPassword] = useState("StrongPass!234");
  const [role, setRole] = useState("manager");
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadUsers = useCallback(async (): Promise<void> => {
    const data = await api.request<ListResponse<AdminUser>>("GET", "/admin/users?limit=100");
    setUsers(data.items);
  }, [api]);

  useEffect(() => { void loadUsers().catch((err) => setError(err instanceof Error ? err.message : "Could not load users.")); }, [loadUsers]);

  const createUser = async (): Promise<void> => {
    setError(null); setSuccess(null); setIsLoading(true);
    try {
      await api.request<AdminUser>("POST", "/admin/users", { username, password, roles: [role], is_superadmin: role === "admin" });
      setSuccess(`Created user ${username}.`);
      setUsername(""); setPassword(""); await loadUsers();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create user."); }
    finally { setIsLoading(false); }
  };

  return <Stack spacing={2.5}><Typography variant="h4">Users</Typography>{success && <StatusBanner severity="success" title="User created" message={success} />}{error && <Alert severity="error">{error}</Alert>}<Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}><Typography variant="h6" sx={{ mb: 2 }}>New user</Typography><Grid container spacing={2}><Grid item xs={12} md={4}><TextField label="Username" value={username} onChange={(event) => setUsername(event.target.value)} fullWidth /></Grid><Grid item xs={12} md={4}><TextField label="Initial password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} fullWidth /></Grid><Grid item xs={12} md={4}><TextField select label="Role" value={role} onChange={(event) => setRole(event.target.value)} fullWidth>{roleOptions.map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</TextField></Grid></Grid><Box sx={{ mt: 2 }}><Button variant="contained" disabled={isLoading || username.length < 3 || password.length < 12} onClick={() => void createUser()}>Create user</Button></Box></Paper><BusinessTable title="User list" rows={users} columns={[{ key: "username", label: "User", render: (item) => item.username },{ key: "roles", label: "Roles", render: (item) => <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>{item.roles.map((userRole) => <Chip key={userRole} label={userRole} size="small" />)}</Stack> },{ key: "active", label: "Status", render: (item) => (item.is_active ? "Active" : "Inactive") },{ key: "admin", label: "Superadmin", render: (item) => (item.is_superadmin ? "Yes" : "No") }]} /></Stack>;
}
