# AWS cost controls and WAF migration

## Evidence and default savings

Read-only audit on 2026-09-19: August unblended totals, including tax, were
$89.35 in prod and $32.03 in test. Prod: Security Hub $22.45, WAF $18.05,
CodeBuild $7.40, CloudWatch $7.24, WorkMail $4.00, KMS $3.97, Config $3.89.
Test: Security Hub $11.92, KMS $4.97, Config $4.70, Secrets Manager $2.00.
These are service totals, not fully avoidable costs. No AWS changes were applied.

- Storage anomaly alarms are now opt-in (enable_storage_anomaly_alarms=false).
  Seven S3/notification-Lambda anomaly alarms per application reported
  INSUFFICIENT_DATA. Validate dimensions, S3 request-metric configuration and
  traffic baseline before re-enabling. Keep Lambda errors, CloudFront 5xx,
  WAF alarms and the availability canary.
- OriginLatency alarms are opt-in (enable_origin_latency_alarms=false).
  All four prod distributions returned NoSuchMonitoringSubscription.
  Missing latency metrics treated as notBreaching do not prove healthy latency.
- Artifact access logs go to existing dedicated infrastructure logging buckets,
  with source-specific prefixes and scoped permissions, avoiding log recursion.
- Automatic infrastructure triggers exclude changes confined to root README.md,
  diagrams/**and docs/**: CodePipeline V2 filters main-branch pushes and the
  GitHub workflow filters non-main pushes. Mixed code/docs commits and manual
  executions still run. This avoids redundant infrastructure builds and their
  downstream application deployments.

Across both repos: fourteen anomaly alarms (three billed metrics each) and four
latency alarms represent approximately $4.60/month before free-tier and
partial-month effects. August total alarm charges were $7.10. S3/build savings
depend on activity; they are not separately quantified.

## Optional shared WAF: approximately $9/month after cleanup

Both ACLs have the same three AWS managed rule groups and a 10,000-request
per-IP rate rule. Website infrastructure owns wafv2-web-acl in us-east-1,
scope CLOUDFRONT, and its logging. CRM reads it by name without mutation rights.
No shared lookup occurs with enable_waf=false.

Sharing combines each IP's website and CRM traffic into one rate counter.
A client below each separate limit can exceed the combined limit. Review this
behavior before opting in. WAF alarms/dashboard dimensions also become shared
traffic. Managed rule groups and their current overrides are preserved.

Defaults shared_waf_web_acl_name=null and retain_dedicated_waf=true retain the
dedicated ACL. The $9 saving begins only after its ACL and four rules are removed.
Request-processing charges remain. Keep the old log group for its 60-day history.

### Preconditions

1. Apply the website owner PR and CRM ci-cd-infrastructure-crm stack first so
   the pipeline role receives discovery permission. Also update crm-iam if using
   the CRM IAM user for plans/applies. Verify the canonical
   ACL and aws-waf-logs-wafv2-web-acl log group exist. The data source requires
   wafv2:ListWebACLs on *, with no new permission to mutate the shared ACL.
2. Generate an authenticated prod plan and reconcile resource addresses, IDs,
   aliases and live primary/staging flags. The read-only state check mapped
   this (primary) to E1EVVKC6CR59FX and staging_cloudfront_distribution to
   E39LTKUHU5LEHB, matching live staging flags. Do not infer roles from origin
   names. Resolve any subsequent mismatch using reviewed Terraform changes.
   Never approve an unexpected primary replacement, origin or DNS change.
3. Prevent concurrent application promotion/infra runs during migration.
   Infra up.yml defers its downstream application trigger while
   WAF_MIGRATION_IN_PROGRESS is true; independent application runs are unaffected.
4. Terraform now owns the primary continuous-deployment association; the
   post-apply distribution_deploy.py call is removed from the infra buildspec.
   Use Terraspace/Terraform only; do not invoke the old WAF-disassociation helper.

### Separate reviewed applies

Commit each row to terraform/app/stacks/crm/tfvars/prod.tfvars, generate a saved
Terraspace plan, review and apply that row, then verify deployment before the next.
Keep enable_waf=true throughout. Never combine stages to reduce build time.

| Stage | enable_cloudfront_staging | attach_continuous_deployment_policy | shared_waf_web_acl_name | retain_dedicated_waf |
| --- | --- | --- | --- | --- |
| Initial | true | true | null | true |
| 1. Detach primary policy | true | false | null | true |
| 2. Remove policy/staging distribution | false | false | null | true |
| 3. Reassociate primary | false | false | "wafv2-web-acl" | true |
| 4. Restore staging and policy | true | false | "wafv2-web-acl" | true |
| 5. Reattach primary policy | true | true | "wafv2-web-acl" | true |
| 6. Remove unused dedicated ACL | true | true | "wafv2-web-acl" | false |

AWS blocks first-time ACL association while continuous deployment is attached.
Both distributions must be Deployed, use the canonical ACL and pass HTTP smoke
tests before stage 6. Verify canonical log delivery and zero remaining old-ACL
associations. Stage 6 destroys only the CRM ACL and logging configuration;
the historical log group, shared ACL and application buckets must remain.
Follow existing saved-plan Terraspace workflows; no console/CLI resource edits.

Before cleanup, rollback uses the same detach/remove/reassociate/restore
sequence with shared_waf_web_acl_name=null. After cleanup, recreate the dedicated
ACL in a separate apply before switching. Never clear enable_waf as a shortcut.

## Remaining costs and verification limits

Security Hub, Config, GuardDuty and bootstrap/Pulumi encryption keys are owned
outside these two repositories. Test key aliases confirm bootstrap operations
and Pulumi encryption. Deleting those keys may make retained data/state unreadable.
Review security-service regions/scope in their owning IaC; do not create competing
Terraform ownership or disable security solely to reduce the bill.
CodeBuild already uses small Linux compute. V2 pipeline costs are action minutes,
not idle fees. Secrets need consumer/rotation ownership checks before retirement.
WorkMail is a separate workload.

Mocked CloudFront tests cover defaults, WAF-disabled test, reassociation retaining
old protection, and cleanup preserving logs. They do not prove live AWS ordering,
IAM access or state alignment. Authenticated plans and staged smoke tests remain
rollout gates. Savings are prospective until deployment and billing verification.

Sources: [CloudFront/WAF restrictions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/continuous-deployment-quotas-considerations.html),
[rate aggregation](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html),
[WAF pricing](https://aws.amazon.com/waf/pricing/),
[S3 recursion](https://docs.aws.amazon.com/AmazonS3/latest/userguide/enable-server-access-logging.html),
[CloudFront metrics](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/viewing-cloudfront-metrics.html).
