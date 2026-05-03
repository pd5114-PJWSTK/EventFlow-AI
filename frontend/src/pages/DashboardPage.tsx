import { Grid, Paper, Stack, Typography } from "@mui/material";

const cards = [
  { title: "Intake AI", desc: "Wpisz opis eventu, zweryfikuj arkusz i zatwierdŸ zapis." },
  { title: "Planner Studio", desc: "Walidacja, generowanie, rekomendacje i decyzja operatora." },
  { title: "Runtime + Replan", desc: "Incydenty live, parse LLM, replan i feed notyfikacji." },
  { title: "Post-Event", desc: "Podsumowanie tekstowe, parse i finalne domkniêcie eventu." },
];

export function DashboardPage(): JSX.Element {
  return (
    <Stack spacing={2}>
      <Typography variant="h4">Panel g³ówny</Typography>
      <Typography color="text.secondary">
        Wszystkie kluczowe funkcjonalnoœci logiczne projektu s¹ dostêpne z paneli bocznych.
      </Typography>
      <Grid container spacing={2}>
        {cards.map((card) => (
          <Grid item xs={12} md={6} key={card.title}>
            <Paper sx={{ p: 3, height: "100%" }}>
              <Typography variant="h6">{card.title}</Typography>
              <Typography color="text.secondary">{card.desc}</Typography>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Stack>
  );
}