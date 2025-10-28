# TODO — Observability (Metrics, Tracing, Logs)

Metrics
- [ ] Expose Streamlit `/health` and custom metrics (if using a sidecar exporter) or scrape container stats.
- [ ] Django Prometheus already enabled — add counters for V2 endpoints (requests, latency, errors) with labels `ui=streamlit_v2`.

Tracing
- [ ] Reuse `utils.tracing` if OTEL is enabled; add `traceparent` propagation from Streamlit requests into Django.
- [ ] Add an HTTP client wrapper in Streamlit to inject `traceparent` on outbound requests to Django.

Logs
- [ ] Ensure Streamlit logs in JSON (or consistent console) with `tenant_id`, `user`, `ui_channel=streamlit_v2`.
- [ ] Django already structured — add fields via DRF auth class middleware binding.

Dashboards
- [ ] Create Grafana/Cloud dashboards for V2 traffic, errors, slow endpoints.

