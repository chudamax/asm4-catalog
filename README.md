# ASM Tools (Skeleton)
/catalog.yaml                        # optional repo metadata (name, apiVersion)
schemas/
  events/*.json                      # JSON Schemas for event types (e.g., dns_domain@v1.json)
tools/
  <tool>/<version>/manifest.yaml     # one folder per version
profiles/
  <slug>.yaml                        # parameter profiles (bind tool@version + resources)
rules/
  scope/*.yaml                       # dynamic scope rules (unified rule DSL)
  promotion/*.yaml                   # event→inventory promotion rules (unified DSL)
  detection/*.yaml                   # ES/KQL detection rules → synthetic findings
playbooks/
  <slug>.yaml                        # steps referencing profiles + scope rules
resources/
  <name>_<version>.*                 # resource artifacts (wordlists, bundles, etc.)
  _index.yaml                        # optional index/meta
monitors/
  *.yaml                             # Monitor Service checks
notifiers/
  channels/*.yaml                    # channel endpoints (slack/email/webhook)
  routes/*.yaml                      # routing rules (what → where → template)
  templates/*.txt                    # message bodies
coverage/
  ledger/*.yaml                      # ledger policies/recency
rbac/
  roles.yaml                         # RBAC role catalog (optional)
quotas/
  *.yaml                             # quota/rate policies (optional)
providers/
  *.yaml                             # (optional) provider profile samples, if you expose them
