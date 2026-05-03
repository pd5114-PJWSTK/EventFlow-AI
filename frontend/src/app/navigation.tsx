import AccountCircleIcon from "@mui/icons-material/AccountCircle";
import AddBusinessIcon from "@mui/icons-material/AddBusiness";
import DashboardIcon from "@mui/icons-material/Dashboard";
import GroupsIcon from "@mui/icons-material/Groups";
import InventoryIcon from "@mui/icons-material/Inventory";
import ManageHistoryIcon from "@mui/icons-material/ManageHistory";
import PostAddIcon from "@mui/icons-material/PostAdd";
import RouteIcon from "@mui/icons-material/Route";

export const navItems = [
  { label: "Dashboard", path: "/dashboard", icon: <DashboardIcon /> },
  { label: "Nowy event", path: "/new-event", icon: <AddBusinessIcon /> },
  { label: "Planowanie eventów", path: "/planning", icon: <RouteIcon /> },
  { label: "Replanowanie live", path: "/replanning", icon: <ManageHistoryIcon /> },
  { label: "Post-event log", path: "/post-event", icon: <PostAddIcon /> },
  { label: "Dane", path: "/data", icon: <InventoryIcon /> },
  { label: "Użytkownicy", path: "/users", icon: <GroupsIcon /> },
  { label: "Moje konto", path: "/me", icon: <AccountCircleIcon /> },
];
