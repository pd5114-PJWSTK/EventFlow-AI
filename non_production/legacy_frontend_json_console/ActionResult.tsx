import { Alert, Paper, Typography } from "@mui/material";

interface ActionResultProps {
  title: string;
  result: unknown;
  error: string | null;
}

export function ActionResult({ title, result, error }: ActionResultProps): JSX.Element {
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 700 }}>
        {title}
      </Typography>
      {error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontSize: 13 }}>{JSON.stringify(result, null, 2)}</pre>
      )}
    </Paper>
  );
}