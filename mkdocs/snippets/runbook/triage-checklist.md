## Triage (first 5 minutes)

- [ ] Acknowledge the alert (note time, `alertname`, namespace/release from ntfy).
- [ ] Check if something changed recently (Git push, chart bump, node drain, storage outage).
- [ ] Confirm the alert is still firing in Prometheus / Grafana (**Alerting** → **Alert rules**).
- [ ] Decide: transient (wait one reconcile interval) vs sustained (continue below).

```bash
# Recent events for the namespace (replace NAMESPACE)
kubectl get events -n NAMESPACE --sort-by='.lastTimestamp' | tail -20
```
