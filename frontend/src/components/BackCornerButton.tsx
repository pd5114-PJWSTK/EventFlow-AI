import ArrowBackIosNewIcon from "@mui/icons-material/ArrowBackIosNew";
import { IconButton, Tooltip } from "@mui/material";

interface BackCornerButtonProps {
  label?: string;
  onClick: () => void;
}

export function BackCornerButton({ label = "Back", onClick }: BackCornerButtonProps): JSX.Element {
  return (
    <Tooltip title={label}>
      <IconButton
        aria-label={label}
        onClick={onClick}
        size="small"
        sx={{ position: "absolute", top: 12, right: 12, zIndex: 2 }}
      >
        <ArrowBackIosNewIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}
