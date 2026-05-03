import { Paper, Typography } from "@mui/material";

interface JsonEditorProps {
  title: string;
  value: string;
  onChange: (next: string) => void;
  minHeight?: number;
}

export function JsonEditor({ title, value, onChange, minHeight = 220 }: JsonEditorProps): JSX.Element {
  return (
    <Paper sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 700 }}>
        {title}
      </Typography>
      <textarea
        style={{
          width: "100%",
          minHeight,
          borderRadius: 12,
          border: "1px solid #d1d5db",
          padding: 12,
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 13,
        }}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </Paper>
  );
}