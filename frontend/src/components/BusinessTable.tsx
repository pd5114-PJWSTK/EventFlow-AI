import { Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";

export interface BusinessColumn<T> {
  key: string;
  label: string;
  render: (item: T) => string | number | JSX.Element;
}

interface BusinessTableProps<T> {
  title?: string;
  columns: BusinessColumn<T>[];
  rows: T[];
  emptyText?: string;
}

export function BusinessTable<T>({ title, columns, rows, emptyText = "No data" }: BusinessTableProps<T>): JSX.Element {
  return (
    <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1, maxWidth: "100%", overflowX: "auto" }}>
      {title && (
        <Typography variant="h6" sx={{ px: 2, pt: 2 }}>
          {title}
        </Typography>
      )}
      <Table size="small" sx={{ minWidth: Math.max(columns.length * 150, 720) }}>
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell key={column.key} sx={{ fontWeight: 700, color: "text.secondary" }}>
                {column.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.length === 0 ? (
            <TableRow>
              <TableCell colSpan={columns.length}>
                <Typography color="text.secondary">{emptyText}</Typography>
              </TableCell>
            </TableRow>
          ) : (
            rows.map((row, index) => (
              <TableRow key={index} hover>
                {columns.map((column) => (
                  <TableCell key={column.key}>{column.render(row)}</TableCell>
                ))}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
