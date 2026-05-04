import { CrudPage } from "./CrudPage";

export function EventsPage(): JSX.Element {
  return (
    <CrudPage
      title="Eventy"
      description="CRUD eventów oraz szybkie testy payloadów planistycznych."
      endpoint="/api/events"
      createTemplate={{
        client_id: "<client_id>",
        location_id: "<location_id>",
        event_name: "Nowy Event",
        event_type: "conference",
        planned_start: "2026-06-20T08:00:00Z",
        planned_end: "2026-06-20T16:00:00Z",
        priority: "medium",
      }}
    />
  );
}