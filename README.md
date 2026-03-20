# Cloud Cost Optimization with AI Enablement

**Author:** Prathamesh Mokal · [linkedin.com/in/prathamesh-mokal](https://linkedin.com/in/prathamesh-mokal)  
**Platform:** AWS · **Assessment:** Senior DevSecOps Engineer — Windmill Digital

---

## What this repo does

Cloud costs go up quietly. Nobody notices until the bill arrives at the end of the month. This repository implements a system that catches waste as it happens — or prevents it from happening at all — rather than reviewing it after the fact.

The approach has four parts:

1. **Terraform infrastructure** — the actual AWS resources that run the cost controls
2. **Automation scripts** — Lambda functions for EBS cleanup, rightsizing PRs, and Config remediation
3. **AI scripts** — Claude API calls for anomaly enrichment, weekly digest, IaC review, and cost forecasting
4. **CI/CD pipeline** — GitHub Actions workflows with security scanning, cost estimation, and safe deployment

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Developer layer                                                 │
│  IDE (Copilot) → GitHub PR → tfsec → Checkov → Semgrep          │
│                           → OPA/Conftest → Infracost → AI review │
└──────────────────────────┬──────────────────────────────────────┘
                           │ terraform apply
┌──────────────────────────▼──────────────────────────────────────┐
│  Data collection                                                 │
│  Cost Explorer · CloudWatch · Compute Optimizer · Tagging API    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ feeds data
┌──────────────────────────▼──────────────────────────────────────┐
│  n8n orchestration (self-hosted)                                 │
│  Anomaly webhook → fetch context → merge → Claude API            │
│  Monday cron    → fetch anomalies + recs → Claude API            │
└──────────────────────────┬──────────────────────────────────────┘
                           │ structured payload
┌──────────────────────────▼──────────────────────────────────────┐
│  AI engine                                                       │
│  Claude API (Anthropic) · Amazon Bedrock (production)            │
│  Anomaly root cause · Weekly digest · IaC review · Forecast      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ approved actions only
┌──────────────────────────▼──────────────────────────────────────┐
│  Automation (Terraform-managed)                                  │
│  EventBridge Scheduler · S3 Lifecycle · EBS Cleanup Lambda       │
│  AWS Config Rules · AWS Budgets · Cost Anomaly Detection         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ alerts + reports
┌──────────────────────────▼──────────────────────────────────────┐
│  Outputs                                                         │
│  Slack alerts · Jira tickets · GitHub PRs · Leadership PDF       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Repository structure

```
cost-optimization-aws/
│
├── README.md
│
├── terraform/
│   ├── main.tf                        # Root module — calls all child modules
│   ├── variables.tf                   # All input variables
│   ├── locals.tf                      # Mandatory tags, computed values
│   ├── outputs.tf                     # Exposed ARNs and values
│   ├── data.tf                        # Data sources (account ID, SSM secrets)
│   ├── providers.tf                   # AWS provider + S3 backend config
│   │
│   ├── environments/
│   │   ├── dev.tfvars                 # Dev environment values
│   │   ├── staging.tfvars             # Staging environment values
│   │   └── prod.tfvars                # Production environment values
│   │
│   └── modules/
│       ├── scheduling/                # Non-prod start/stop via EventBridge
│       ├── storage-lifecycle/         # S3 tiering + EBS orphan cleanup Lambda
│       ├── budgets/                   # SNS alerts + AWS Budgets per team
│       ├── governance/                # Config rules + Security Hub + rightsizing Lambda
│       └── anomaly-detection/         # AWS Cost Anomaly Detection
│
├── scripts/
│   ├── lambda/
│   │   ├── ebs_cleanup.py             # Finds orphan EBS volumes + old snapshots weekly
│   │   ├── rightsizing_pr.py          # Reads Compute Optimizer, opens GitHub PR
│   │   └── config_remediation.py      # Auto-tags non-compliant resources
│   │
│   ├── ai/
│   │   ├── anomaly_enrichment.py      # Claude API: spike → root cause + recommended fix
│   │   ├── weekly_digest.py           # Claude API: weekly cost report → ranked actions
│   │   ├── iac_review.py              # Claude API: terraform plan → PR cost comment
│   │   └── forecast_narrative.py      # Claude API: forecast numbers → CFO paragraph
│   │
│   └── n8n/
│       ├── anomaly_enrichment.json    # n8n workflow: SNS alert → Claude → Slack + Jira
│       └── weekly_digest.json         # n8n workflow: Monday cron → Claude → Slack + email
│
├── policies/
│   ├── cost.rego                      # OPA: cost + security guardrails on terraform plan
│   └── .semgrep/
│       └── cost-rules.yml             # Custom Semgrep rules for cost and security
│
└── .github/
    └── workflows/
        ├── security-scan.yml          # tfsec + Checkov + Semgrep on every PR
        ├── terraform-plan.yml         # OPA + Infracost + AI review on every PR
        └── terraform-apply.yml        # Safe apply on merge to main
```

---

## CI/CD pipeline

Every pull request touching Terraform runs this sequence. All checks must pass before a human reviews.

```
PR opened
    │
    ├── security-scan.yml
    │   ├── tfsec          — security static analysis (HIGH severity blocks PR)
    │   ├── Checkov        — misconfiguration scan (HIGH severity blocks PR)
    │   └── Semgrep        — custom cost + security rules
    │       └── SARIF → GitHub Security tab + AWS Security Hub
    │
    └── terraform-plan.yml
        ├── OPA/Conftest   — policy-as-code: blocks oversized instances,
        │                    missing tags, unencrypted resources, Multi-AZ in non-prod
        ├── Infracost      — posts monthly cost diff as PR comment
        │                    blocks PR if cost increase > $500/month
        └── AI cost review — sends plan to Claude API, posts suggestions as PR comment
```

On merge to `main`:

```
terraform-apply.yml
    ├── terraform init  (environment-specific state key)
    ├── terraform validate
    ├── terraform plan  -var-file=environments/{env}.tfvars
    └── terraform apply
        ├── Success → Slack notification
        └── Failure → Slack alert with run link
```

Production deployments require manual approval configured in GitHub Environments settings.

---

## What gets saved

| What | Estimated saving | When |
|------|-----------------|------|
| Turning off non-prod servers overnight | 40–65% of non-prod compute | Immediately |
| Downsizing oversized servers | 15–30% of compute spend | Month 2–3 |
| Storage tiering and cleanup | 20–40% of storage spend | Month 1–2 |
| Switching to Savings Plans | 30–40% vs pay-as-you-go | Month 2–4 |
| Catching unexpected spend early | 5–15% waste avoided | Ongoing |

---

## How to deploy

**Prerequisites:**
- AWS account with appropriate permissions
- S3 bucket and DynamoDB table for Terraform state
- SSM Parameter Store entries for secrets (see below)
- GitHub repository secrets configured

**Required SSM parameters:**
```
/cost-optimization/{env}/anthropic-api-key   # Claude API key
/cost-optimization/{env}/github-token         # GitHub token for PR automation
```

**Required GitHub secrets:**
```
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
ANTHROPIC_API_KEY
INFRACOST_API_KEY
SEMGREP_APP_TOKEN
SLACK_WEBHOOK_URL
```

**Deploy to dev:**
```bash
cd terraform
terraform init -backend-config="key=cost-optimization/dev/terraform.tfstate"
terraform plan -var-file="environments/dev.tfvars"
terraform apply -var-file="environments/dev.tfvars"
```

**Deploy to staging:**
```bash
terraform init -backend-config="key=cost-optimization/staging/terraform.tfstate"
terraform plan -var-file="environments/staging.tfvars"
terraform apply -var-file="environments/staging.tfvars"
```

**Deploy to prod:**
```bash
terraform init -backend-config="key=cost-optimization/prod/terraform.tfstate"
terraform plan -var-file="environments/prod.tfvars"
# Requires senior engineer approval before apply
terraform apply -var-file="environments/prod.tfvars"
```

---

## AI integration

AI is used for analysis and recommendations. It never executes changes.

**How it works:**

When an anomaly alert fires, an n8n workflow fetches CloudWatch metrics, recent GitHub deployments, and resource ownership. All of that is sent to the Claude API with a structured prompt. The response — root cause, recommended action, estimated saving, risk level — appears in Slack within two minutes. The same approach runs every Monday for a weekly digest.

Every Terraform PR gets an AI cost review — the plan is sent to Claude and suggestions appear as a PR comment alongside the Infracost estimate.

**Validation before any action is taken:**

1. Automated sense check — Lambda verifies the recommendation is coherent before showing it to anyone
2. Two-engineer Slack approval — two engineers must approve before anything moves
3. 48-hour staging test — infrastructure changes are applied to staging and monitored before production

The AI never triggers a Terraform apply directly.

---

## Security

- All automation roles use resource-scoped IAM policies — no wildcard actions
- S3 buckets use KMS SSE with bucket key enabled
- SNS topics and Lambda environment variables are encrypted
- All secrets stored in SSM Parameter Store — never in code or tfvars
- tfsec, Checkov, and Semgrep findings uploaded to AWS Security Hub via SARIF
- All actions logged to CloudTrail
- Reviewed in monthly security posture meeting

---

*Prathamesh Mokal · AWS Certified Security Specialty · Terraform Associate · 8 years DevSecOps / SRE*
