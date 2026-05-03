import { Alert, Chip, Stack, Typography } from "@mui/material";

interface StatusBannerProps {
  severity?: "success" | "info" | "warning" | "error";
  title: string;
  message?: string;
  source?: string;
}

export function StatusBanner({ severity = "info", title, message, source }: StatusBannerProps): JSX.Element {
  return (
    <Alert severity={severity} sx={{ borderRadius: 2 }}>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ xs: "flex-start", sm: "center" }}>
        <Typography fontWeight={700}>{title}</Typography>
        {message && <Typography>{message}</Typography>}
        {source && <Chip size="small" label={source} variant="outlined" />}
      </Stack>
    </Alert>
  );
}
