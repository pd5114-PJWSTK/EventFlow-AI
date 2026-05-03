import { CrudPage } from "./CrudPage";

export function ResourcesPage(): JSX.Element {
  return (
    <CrudPage
      title="Zasoby"
      description="Panel operacji na zasobach (domyœlnie people)."
      endpoint="/api/resources/people"
      createTemplate={{
        full_name: "Nowa osoba",
        role: "coordinator",
        home_base_location_id: "<location_id>",
        cost_per_hour: 110,
      }}
    />
  );
}