# api

A versioned FastAPI service. Serves verdict requests (running the agents
through the cache) and reads evaluation metrics from the semantic layer.
The web app never queries the warehouse or calls an LLM directly.

Key routes: `POST /v1/verdicts`, `GET /v1/verdicts/{id}`,
`GET /v1/metrics/{name}`, `GET /v1/experiments`, `GET /v1/traces/{run_id}`.
All routes share one error schema and are described by an OpenAPI spec
that generates the web app's TypeScript types.
