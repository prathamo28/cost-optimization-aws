# cost-optimization-aws

![Terraform](https://img.shields.io/badge/Terraform-1.5+-7B42BC?logo=terraform&logoColor=white)
![AWS](https://img.shields.io/badge/AWS-eu--west--1-FF9900?logo=amazonaws&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Security](https://img.shields.io/badge/Security-tfsec%20%7C%20Checkov%20%7C%20Semgrep%20%7C%20OPA-red)

**Author:** Prathamesh Mokal · [linkedin.com/in/prathamesh-mokal](https://linkedin.com/in/prathamesh-mokal)  
AWS Certified Security Specialty · Terraform Associate · 8 years DevSecOps / SRE

---

## The problem this solves

Cloud costs go up quietly. Nobody notices until the bill arrives. By then it is too late — the waste has already happened, and nobody can easily explain what caused it.

This repository implements a system that catches waste as it happens. Servers that should not be running overnight get turned off automatically. Servers that are too big for what they are doing get flagged and resized. Old files that have not been touched in months get moved to cheaper storage. And when something unexpected happens — a sudden spike in spend — an AI workflow investigates it automatically and posts an explanation to Slack in under two minutes.

Everything is Terraform. Every change goes through a security and cost pipeline before it touches infrastructure. Nothing changes in production without a human approving it first.

---

## Architecture

> See `architecture.drawio` — import directly into [draw.io](https://draw.io) for the full interactive diagram with all AWS service icons.

**Four layers:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  CI/CD & Developer Layer                                            │
│                                                                     │
│  GitHub PR → tfsec → Checkov → Semgrep → OPA → Infracost           │
│           → AI IaC review (Claude API → PR comment)                │
│  Environments: dev.tfvars · staging.tfvars · prod.tfvars            │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ terraform apply
┌───────────────────────────▼─────────────────────────────────────────┐
│  AWS Services                                                       │
│                                                                     │
│  Cost Explorer · CloudWatch · Compute Optimizer · Tagging API       │
│  EventBridge Scheduler · S3 Lifecycle · AWS Budgets · Config        │
│  SCPs · Cost Anomaly Detection · Security Hub · CloudTrail          │
│  Lambda (EBS cleanup · rightsizing · remediation) · Forecast        │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ SNS anomaly alert / Monday cron
┌───────────────────────────▼─────────────────────────────────────────┐
│  n8n Orchestration (self-hosted — data stays in VPC)                │
│                                                                     │
│  Flow 1 (event): SNS → fetch CW + GitHub + Tags → Claude → Slack   │
│  Flow 2 (weekly): Cost Explorer + Optimizer → Claude → Slack + PDF │
│  Validation: sense check → 2-engineer approval → 48h staging       │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ alerts / reports / PRs
┌───────────────────────────▼─────────────────────────────────────────┐
│  Outputs                                                            │
│  Slack · Jira · GitHub PRs · QuickSight · Leadership PDF · Pager   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Repository structure

```
cost-optimization-aws/
│
├── architecture.drawio              ← Full diagram — open in draw.io
├── README.md
│
├── terraform/
│   ├── main.tf                      ← Root module
│   ├── variables.tf
│   ├── locals.tf                    ← Mandatory tags, name prefix
│   ├── outputs.tf
│   ├── data.tf                      ← SSM secret fetches
│   ├── providers.tf                 ← AWS provider + S3 backend
│   │
│   ├── environments/
│   │   ├── dev.tfvars
│   │   ├── staging.tfvars
│   │   └── prod.tfvars              ← Scheduling OFF, higher thresholds
│   │
│   └── modules/
│       ├── scheduling/              ← Stop 20:00 · Start 07:00 (non-prod only)
│       ├── storage-lifecycle/       ← S3 tiering + EBS cleanup Lambda
│       ├── budgets/                 ← SNS + AWS Budgets 80%/100% alerts
│       ├── governance/              ← Config rules · Security Hub · rightsizing Lambda
│       └── anomaly-detection/       ← Cost Anomaly Detection + SNS subscription
│
├── scripts/
│   ├── lambda/
│   │   ├── ebs_cleanup.py           ← Weekly: orphan volumes + old snapshots
│   │   ├── rightsizing_pr.py        ← Weekly: Compute Optimizer → GitHub PR
│   │   └── config_remediation.py    ← Auto-tag non-compliant resources
│   │
│   ├── ai/
│   │   ├── anomaly_enrichment.py    ← Claude API: spike → root cause + fix
│   │   ├── weekly_digest.py         ← Claude API: weekly report → ranked actions
│   │   ├── iac_review.py            ← Claude API: tf plan → PR cost comment
│   │   └── forecast_narrative.py    ← Claude API: forecast → CFO paragraph
│   │
│   └── n8n/
│       ├── anomaly_enrichment.json  ← Import directly into n8n
│       └── weekly_digest.json       ← Import directly into n8n
│
├── policies/
│   ├── cost.rego                    ← OPA: 7 rules on terraform plan
│   └── .semgrep/
│       └── cost-rules.yml           ← Custom rules: oversized instances, missing tags, secrets
│
└── .github/
    └── workflows/
        ├── security-scan.yml        ← tfsec + Checkov + Semgrep → SARIF → Security Hub
        ├── terraform-plan.yml       ← OPA + Infracost + AI review on every PR
        └── terraform-apply.yml      ← init → validate → plan → apply → Slack notify
```

---

## CI/CD pipeline

Every pull request touching Terraform runs this in sequence. All checks must pass before a human reviews.

```
PR opened
    │
    ├── security-scan.yml
    │   ├── tfsec     ── security static analysis ── HIGH severity blocks PR
    │   ├── Checkov   ── misconfiguration scan ────── HIGH severity blocks PR
    │   └── Semgrep   ── custom cost + security rules
    │         └── SARIF → GitHub Security tab + AWS Security Hub
    │
    └── terraform-plan.yml
        ├── OPA/Conftest ── policy check on plan JSON
        │     Blocks: oversized non-prod instances · missing tags · Multi-AZ RDS in staging
        │             unencrypted EBS · Lambda without tracing · unencrypted SNS
        ├── Infracost ───── cost diff as PR comment · blocks if increase > $500/month
        └── AI review ───── plan → Claude API → suggestions as PR comment

On merge to main:
    terraform init → validate → plan -var-file=environments/{env}.tfvars → apply
    └── Slack: success or failure with run link
```

Production requires manual approval configured in GitHub Environments settings.

---

## What gets saved

| Initiative | Estimated saving | When |
|---|---|---|
| Turning off non-prod servers overnight | 40–65% of non-prod compute | Immediately |
| Downsizing oversized servers | 15–30% of compute spend | Month 2–3 |
| S3 tiering + EBS cleanup | 20–40% of storage spend | Month 1–2 |
| Savings Plans instead of On-Demand | 30–40% of baseline compute | Month 2–4 |
| AI anomaly detection + prevention | 5–15% waste avoided | Ongoing |

---

## AI integration

AI is used for analysis and recommendations. It never executes changes.

**Anomaly enrichment** — when an alert fires, n8n fetches CloudWatch metrics, recent deployments from GitHub, and resource ownership. All of it goes to the Claude API. Root cause and fix appear in Slack in under two minutes. Same investigation done manually takes 30–45 minutes.

**Weekly digest** — every Monday 08:00, top anomalies and Compute Optimizer recommendations go to Claude. Ranked action list posted to Slack, PDF emailed to leadership.

**IaC review** — every Terraform PR gets an AI cost review. Plan sent to Claude, suggestions appear as PR comment alongside Infracost.

**Forecast** — Amazon Forecast generates 30/60/90-day predictions. Claude turns the numbers into plain English for the monthly leadership report.

**Before any recommendation is acted on:**
1. Automated sense check — Lambda verifies the recommendation makes basic sense
2. Two engineers approve in Slack
3. Change applied to staging, monitored for 48 hours
4. Production PR raised only after staging passes

The Claude API never triggers a Terraform apply directly. Production uses Amazon Bedrock — data stays within the AWS account boundary and is not used for model training.

---

## How to deploy

**Prerequisites**
- AWS account with appropriate permissions
- S3 bucket and DynamoDB table for Terraform state
- n8n instance (self-hosted, inside VPC)
- Secrets in SSM Parameter Store:
```
/cost-optimization/{env}/anthropic-api-key
/cost-optimization/{env}/github-token
```

**GitHub repository secrets**
```
AWS_ACCESS_KEY_ID · AWS_SECRET_ACCESS_KEY · ANTHROPIC_API_KEY
INFRACOST_API_KEY · SEMGREP_APP_TOKEN · SLACK_WEBHOOK_URL
```

**Deploy**
```bash
cd terraform

# Dev
terraform init -backend-config="key=cost-optimization/dev/terraform.tfstate" \
               -backend-config="bucket=your-tfstate-bucket" \
               -backend-config="region=eu-west-1"
terraform apply -var-file="environments/dev.tfvars"

# Staging
terraform init -backend-config="key=cost-optimization/staging/terraform.tfstate"
terraform apply -var-file="environments/staging.tfvars"

# Prod (requires senior approval)
terraform init -backend-config="key=cost-optimization/prod/terraform.tfstate"
terraform apply -var-file="environments/prod.tfvars"
```

**Import n8n workflows**
```
n8n → Workflows → Import from file
→ scripts/n8n/anomaly_enrichment.json
→ scripts/n8n/weekly_digest.json
```
Update credentials (SNS, Slack, Jira, Anthropic) in each workflow after importing.

---

## Security

- All IAM roles use resource-scoped policies — no wildcard actions
- S3 buckets: KMS SSE with bucket key (reduces KMS API cost ~99%)
- SNS topics and Lambda environment variables encrypted
- Secrets in SSM Parameter Store — never in `.tfvars` or code
- tfsec + Checkov findings → SARIF → GitHub Security + AWS Security Hub
- All automation actions logged to CloudTrail

---

## DevSecOps tools

| Tool | Purpose | Where |
|---|---|---|
| tfsec | Security static analysis | CI/CD — every PR |
| Checkov | Misconfiguration scanning | CI/CD — every PR |
| Semgrep | Custom cost + security rules | CI/CD — every PR |
| OPA / Conftest | Policy-as-code on plan JSON | CI/CD — every PR |
| Infracost | Monthly cost diff on PR | CI/CD — every PR |
| AWS Config | Continuous tag compliance | Runtime — always on |
| AWS Security Hub | Aggregated findings | Runtime — always on |
| CloudTrail | Audit log for automation | Runtime — always on |

---

*Prathamesh Mokal · AWS Certified Security Specialty · Terraform Associate · 8 years DevSecOps / SRE*  
*[linkedin.com/in/prathamesh-mokal](https://linkedin.com/in/prathamesh-mokal)*
