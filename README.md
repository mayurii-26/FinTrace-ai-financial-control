# ⚡ FinTrace • AI Financial Control & Exception Intelligence

> **Razorpay Buildathon 2026 — Track 04: AI Finance Controller**
>
> **Deterministic finance. Probabilistic intelligence. Verified resolution.**

FinTrace is an AI-powered financial control platform that reconstructs end-to-end transaction lifecycles, detects financial control breaks, quantifies monetary exposure, investigates exceptions using evidence-backed AI, and verifies resolution through a human-in-the-loop workflow.

---

## 📑 Table of Contents

- [Executive Summary](#-executive-summary)
- [The Problem](#️-the-problem)
- [Our Solution](#-our-solution)
- [Core Operating Loop](#-core-operating-loop)
- [What Makes FinTrace Different](#-what-makes-fintrace-different)
- [System Architecture](#️-system-architecture)
- [AI Investigation Layer](#-ai-investigation-layer)
- [Human-in-the-Loop Resolution](#-human-in-the-loop-resolution)
- [Verification & Audit Trail](#-verification--audit-trail)
- [Synthetic Dataset & Ground Truth](#-synthetic-dataset--ground-truth)
- [Benchmarking & Evaluation](#-benchmarking--evaluation)
- [Authentication & Security](#-authentication--security)
- [Razorpay Integration](#-razorpay-integration)
- [Technology Stack](#-technology-stack)
- [API Overview](#-api-overview)
- [Quick Start](#-quick-start)
- [Seed 600 Evaluation Records](#-seed-600-evaluation-records)
- [Run the Benchmark](#-run-the-benchmark)
- [Run Tests](#-run-tests)
- [Judge Demo Flow](#-judge-demo-flow)
- [Project Structure](#-project-structure)
- [Design Principles](#-design-principles)
- [Future Extensions](#-future-extensions)
- [Why FinTrace Fits Track 04](#-why-fintrace-fits-track-04)

---

## 🎯 Executive Summary

Financial operations are rarely broken because a single transaction is missing.

The real problem is that a transaction passes through multiple financial stages:

```
ORDER
   ↓
PAYMENT
   ↓
REFUND
   ↓
FEE / TAX
   ↓
EXPECTED SETTLEMENT
   ↓
ACTUAL SETTLEMENT
   ↓
BANK CREDIT
```

A financial controller therefore needs to answer much more than:

> "Did the payment succeed?"

They need to answer:

> **"DID THE ENTIRE FINANCIAL LIFECYCLE REMAIN CORRECT FROM SOURCE TRANSACTION TO FINAL BANK CREDIT?"**

FinTrace is built around this idea. It creates a Financial Lifecycle Trace for every transaction, detects where the financial chain breaks, calculates the exact monetary exposure, investigates the exception using evidence-backed AI, allows a controller to take an explicit action, and finally reruns the control to verify whether the issue was actually resolved.

---

## ⚠️ The Problem

Modern payment systems generate financial records across multiple operational systems.

A single customer transaction can result in:

- An order record
- A payment record
- Fees and taxes
- A refund
- An expected settlement
- An actual settlement
- A bank credit

These records can become inconsistent because of:

- Missing downstream events
- Duplicate financial events
- Settlement amount discrepancies
- Refund lifecycle failures
- Timing anomalies
- Orphan financial records
- Partial or delayed updates

Traditional reconciliation approaches generally answer:

> "Which records don't match?"

FinTrace goes further:

> **"WHERE DID THE FINANCIAL LIFECYCLE BREAK, HOW MUCH MONEY IS EXPOSED, WHY DID IT HAPPEN, WHAT EVIDENCE SUPPORTS THE DIAGNOSIS, WHAT SHOULD THE CONTROLLER DO, AND DID THE CORRECTION ACTUALLY WORK?"**

---

## 🚀 Our Solution

FinTrace combines a deterministic financial control engine with an AI investigation layer.

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         FINTRACE                                     │
│              AI FINANCIAL CONTROL PLATFORM                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Synthetic / Financial Records                                       │
│                                                                      │
│   Orders     Payments     Refunds     Fees/Tax     Settlements       │
│      │          │            │            │              │            │
│      └──────────┴────────────┴────────────┴──────────────┘            │
│                              │                                       │
│                              ▼                                       │
│               ┌──────────────────────────────┐                       │
│               │  DETERMINISTIC CONTROL       │                       │
│               │       ENGINE                 │                       │
│               │                              │                       │
│               │  • Lifecycle validation      │                       │
│               │  • Financial consistency     │                       │
│               │  • Exception detection       │                       │
│               │  • Exposure calculation      │                       │
│               └──────────────┬───────────────┘                       │
│                              │                                       │
│                        Exceptions                                    │
│                              │                                       │
│                              ▼                                       │
│               ┌──────────────────────────────┐                       │
│               │   AI INVESTIGATION LAYER     │                       │
│               │                              │                       │
│               │  • Read-only finance tools   │                       │
│               │  • Evidence retrieval        │                       │
│               │  • Root-cause analysis       │                       │
│               │  • Confidence scoring        │                       │
│               │  • Recommendations           │                       │
│               └──────────────┬───────────────┘                       │
│                              │                                       │
│                              ▼                                       │
│               ┌──────────────────────────────┐                       │
│               │  CONTROLLER ACTION           │                       │
│               │                              │                       │
│               │  APPROVE / REJECT / ESCALATE │                       │
│               └──────────────┬───────────────┘                       │
│                              │                                       │
│                              ▼                                       │
│               ┌──────────────────────────────┐                       │
│               │      VERIFICATION            │                       │
│               │                              │                       │
│               │  Rerun deterministic checks  │                       │
│               │  Compare exposure            │                       │
│               │  VERIFIED / FAILED           │                       │
│               └──────────────┬───────────────┘                       │
│                              │                                       │
│                              ▼                                       │
│                       AUDIT TRAIL                                   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Core Operating Loop

FinTrace closes the complete finance-control loop:

```
INGEST
   ↓
CONTROL
   ↓
DETECT
   ↓
QUANTIFY
   ↓
INVESTIGATE
   ↓
RECOMMEND
   ↓
CONTROLLER ACTION
   ↓
VERIFY
```

### 1. INGEST

Financial records are loaded into the relational database.

The evaluation environment generates a controlled synthetic dataset containing hundreds of financial lifecycle records.

### 2. CONTROL

The deterministic engine validates relationships between financial entities.

All monetary calculations use Python `Decimal` arithmetic.

The LLM is **never used as the authoritative source for financial calculations**.

### 3. DETECT

Control failures are converted into structured exceptions.

Examples include:

- Settlement amount discrepancies
- Refund closure failures
- Duplicate financial events
- Orphan financial events
- Settlement timing anomalies
- Missing downstream events

### 4. QUANTIFY

Every exception is assigned a monetary exposure.

This lets a finance controller prioritize:

> **₹1 lakh exposure with one exception**

over

> **₹100 exposure with ten exceptions**

The system therefore prioritizes **financial impact, not just exception count**.

### 5. INVESTIGATE

The AI investigator retrieves evidence from the database through read-only tools.

It builds an evidence-backed explanation of the exception.

### 6. CONTROLLER ACTION

The controller can:

```text
APPROVE
REJECT
ESCALATE
```

The AI does not independently mutate financial records.

### 7. VERIFY

After an action, FinTrace reruns the deterministic financial controls.

The system compares:

```
BEFORE EXPOSURE
        ↓
CONTROLLER ACTION
        ↓
AFTER EXPOSURE
```

The exception becomes **VERIFIED** only when the deterministic verification succeeds.

---

## ⭐ What Makes FinTrace Different

### 1. Financial Lifecycle Integrity

Most reconciliation systems focus on individual mismatches.

FinTrace reconstructs the entire financial lifecycle:

```
ORDER
  ↓
PAYMENT
  ↓
REFUND
  ↓
FEE/TAX
  ↓
EXPECTED SETTLEMENT
  ↓
ACTUAL SETTLEMENT
  ↓
BANK CREDIT
```

This allows the controller to see where the financial chain broke.

### 2. Financial Exposure Prioritization

Exceptions are ranked by monetary impact.

```
Priority Score
      ↓
Financial Exposure
      +
Severity
      +
Evidence Confidence
```

This transforms a large exception queue into an actionable control dashboard.

### 3. Evidence-Backed AI

FinTrace does not ask the LLM to "look at the database."

Instead, the AI receives controlled tools such as:

```text
get_transaction()
get_payment_details()
get_refund_details()
get_settlement_details()
get_bank_entry()
get_financial_timeline()
```

The AI must base its conclusion on retrieved evidence.

### 4. Confidence-Aware Decisions

AI recommendations contain an explicit confidence value.

| Confidence Range | Classification | Action |
|---|---|---|
| ≥ 0.90 | HIGH CONFIDENCE | Recommendation can be presented clearly |
| 0.70 – < 0.90 | CONTROLLER VERIFICATION | Human verification required |
| < 0.70 | INSUFFICIENT EVIDENCE | Manual investigation required |

The system does not treat every AI answer as equally reliable.

### 5. Human-in-the-Loop

FinTrace is designed as a controller assistant, not an uncontrolled autonomous financial actor.

The AI can:

- Investigate
- Retrieve evidence
- Identify probable root cause
- Recommend action

The controller remains responsible for consequential actions.

### 6. Closed-Loop Verification

The workflow does not stop at "AI says the issue is fixed." It verifies the financial state again.

```
DETECTED
   ↓
INVESTIGATED
   ↓
ACTION
   ↓
RERUN CONTROL
   ↓
VERIFIED / FAILED
```

This makes verification measurable and auditable.

---

## 🏛️ System Architecture

```text
                         ┌───────────────────────┐
                         │      React + Vite      │
                         │    FinTrace Console    │
                         └───────────┬───────────┘
                                     │
                              REST / JWT
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │      FastAPI API       │
                         └───────────┬───────────┘
                                     │
                 ┌───────────────────┼──────────────────┐
                 │                   │                  │
                 ▼                   ▼                  ▼
       ┌────────────────┐  ┌─────────────────┐  ┌───────────────┐
       │ Control Engine │  │ AI Investigation│  │ Audit System  │
       │                │  │     Agent       │  │               │
       │ Decimal Math   │  │ OpenAI / Mock   │  │ Event Trail   │
       │ Detection      │  │ Read-only Tools │  │               │
       └───────┬────────┘  └────────┬────────┘  └───────┬───────┘
               │                    │                   │
               └────────────────────┼───────────────────┘
                                    │
                                    ▼
                         ┌───────────────────────┐
                         │ Supabase PostgreSQL   │
                         │                       │
                         │ Orders                │
                         │ Payments              │
                         │ Refunds               │
                         │ Settlements           │
                         │ Bank Entries          │
                         │ Exceptions            │
                         │ Investigations        │
                         │ Audit Logs             │
                         └───────────────────────┘
```

### 🔍 Financial Lifecycle Trace

The central FinTrace visualization is the Financial Lifecycle Trace.

For each exception, the controller can inspect:

```
ORDER
   │
   ├── VALID
   │
PAYMENT
   │
   ├── VALID
   │
FEE & TAX
   │
   ├── VALID
   │
EXPECTED SETTLEMENT
   │
   ├── VALID
   │
ACTUAL SETTLEMENT
   │
   └── BREAK
         │
BANK CREDIT
   │
   └── MISSING / WARNING
```

Each stage can be classified as:

- VALID
- WARNING
- BREAK
- MISSING

This provides a visual explanation of the exact location of a financial control failure.

### 🧮 Deterministic Financial Control Engine

The control engine is the authoritative financial layer.

**Design principle:** Deterministic finance. Probabilistic intelligence.

The control engine is responsible for:

- Financial arithmetic
- Expected amount calculations
- Fee/tax calculations
- Lifecycle consistency
- Exception classification
- Monetary exposure
- Verification

The AI is not responsible for these calculations.

### Control Scenarios

FinTrace generates and detects multiple controlled scenarios:

**HEALTHY**
Complete and internally consistent lifecycle.

**SETTLEMENT_AMOUNT_DISCREPANCY**
Expected settlement and actual settlement differ beyond the configured tolerance.

**REFUND_CLOSURE_FAILURE**
A refund occurs but the downstream financial lifecycle is incomplete or inconsistent.

**DUPLICATE_FINANCIAL_EVENT**
Multiple financial events exist where only one should exist.

**ORPHAN_FINANCIAL_EVENT**
A financial record exists without the corresponding upstream lifecycle event.

**SETTLEMENT_TIMING_ANOMALY**
The financial event occurs outside the expected lifecycle timing.

**MISSING_DOWNSTREAM_EVENT**
An upstream event exists but its expected downstream financial event is absent.

---

## 🤖 AI Investigation Layer

FinTrace supports a real OpenAI-powered investigation layer.

The AI operates on top of the deterministic control engine.

### Investigation Process

```text
Exception Detected
       ↓
Retrieve Transaction Context
       ↓
Call Read-Only Finance Tools
       ↓
Build Evidence Set
       ↓
Identify Root Cause
       ↓
Estimate Confidence
       ↓
Generate Recommendation
       ↓
Controller Review
```

### AI Investigation Output

The investigation returns structured information:

- Exception Type
- Severity
- Root Cause
- Evidence
- Missing Evidence
- Confidence
- Recommendation
- Recommended Action
- Human Review Requirement

This ensures the AI output is machine-readable and auditable.

### AI Safety Rules

The AI:

- Cannot directly modify financial records
- Cannot create money values
- Cannot override deterministic calculations
- Cannot invent missing evidence
- Cannot claim certainty when evidence is insufficient
- Must use available evidence before forming a conclusion
- Must escalate low-confidence cases

---

## 👤 Human-in-the-Loop Resolution

Every consequential action passes through the controller.

Supported actions:

```
APPROVE
REJECT
ESCALATE
```

The action is stored with:

- Exception ID
- Controller action
- Timestamp
- AI recommendation
- Investigation evidence
- Confidence
- Verification result

This creates an auditable chain from detection to resolution.

---

## ✅ Verification & Audit Trail

Verification is performed by rerunning the deterministic control engine.

```
BEFORE
────────────────────────
Exposure: ₹72,582.94

        ↓

CONTROLLER ACTION

        ↓

AFTER
────────────────────────
Exposure: ₹0.00

        ↓

VERIFICATION

        ↓

VERIFIED
```

A successful verification is not based on the AI's opinion. It is based on the deterministic financial state after the action.

### Audit Trail

FinTrace records operational events such as:

- Exception detected
- Investigation started
- Tool executed
- AI conclusion generated
- Controller action recorded
- Verification executed
- Verification result recorded

This provides traceability for financial-control operations.

---

## 📊 Synthetic Dataset & Ground Truth

FinTrace includes a deterministic synthetic data generator for reproducible evaluation.

The evaluation dataset contains:

```text
Orders
Payments
Refunds
Fees / Taxes
Settlements
Bank Entries
```

Each generated dataset has a corresponding ground-truth classification.

This allows FinTrace to measure detection quality instead of presenting only visual results.

### Reproducibility

The default configuration uses:

```
SYNTHETIC_RECORD_COUNT=600
SYNTHETIC_SEED=42
```

Using the same seed produces a reproducible evaluation dataset.

---

## 📈 Benchmarking & Evaluation

FinTrace measures both operational throughput and detection quality.

### Metrics

- Total Records
- Healthy Records
- Detected Exceptions
- Match Rate
- Precision
- Recall
- F1 Score
- Processing Throughput
- Total Financial Value
- Total Financial Exposure
- Auto-Resolved Exceptions
- Unresolved Exceptions
- Resolution Rate

### Important Evaluation Principle

The benchmark is generated from ground truth.

No benchmark values are hardcoded.

Throughput is measured using runtime timing rather than a manually entered number.

For example:

```python
start = time.perf_counter()

run_control_engine()

elapsed = time.perf_counter() - start

throughput = records_processed / elapsed
```

This allows FinTrace to report reproducible benchmark measurements based on the actual execution environment.

---

## 🔐 Authentication & Security

FinTrace uses Supabase Authentication for application access.

### Authentication Flow

```text
User
 ↓
Supabase Auth
 ↓
JWT Session
 ↓
Frontend API Client
 ↓
FastAPI
```

The frontend automatically attaches the active Supabase access token to API requests.

### Security Principles

**Secrets stay server-side**

Sensitive credentials such as:

```
OPENAI_API_KEY
RAZORPAY_KEY_SECRET
DATABASE_URL
```

must never be placed in the frontend.

Only public Supabase client configuration belongs in the frontend environment.

**Database Security**

Supabase PostgreSQL is used as the production-style relational database.

Row Level Security can remain enabled in Supabase.

The FastAPI backend connects through the configured backend database connection.

---

## 💳 Razorpay Integration

FinTrace includes a Razorpay integration layer designed for Test Mode.

The integration is intentionally separated from the core deterministic evaluation engine.

This allows the project to demonstrate Razorpay compatibility without requiring live financial transactions during evaluation.

Configuration:

```
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_MODE=test
```

The Razorpay SDK is available through the backend integration layer.

> **Important:** FinTrace does not require live-money operations for the benchmark. The synthetic financial-control dataset is the authoritative evaluation environment.

---

## 🧰 Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript |
| Build Tool | Vite |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Icons | Lucide |
| Backend | FastAPI |
| Language | Python |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Database | Supabase PostgreSQL |
| Authentication | Supabase Auth |
| AI | OpenAI API |
| Financial Arithmetic | Python Decimal |
| Synthetic Data | Faker / NumPy / Pandas |
| Advisory Anomaly Scoring | Isolation Forest |
| Payments Integration | Razorpay Python SDK |
| Testing | Pytest |
| API Documentation | FastAPI Swagger |

---

## 📡 API Overview

FastAPI automatically exposes interactive API documentation.

After starting the backend:

```text
http://127.0.0.1:8000/docs
```

### Core Endpoints

```text
GET    /api/health
POST   /api/seed

GET    /api/exceptions
GET    /api/exceptions/{exception_id}

POST   /api/exceptions/{exception_id}/investigate

POST   /api/exceptions/{exception_id}/action

POST   /api/exceptions/{exception_id}/verify

GET    /api/exceptions/{exception_id}/trace

GET    /api/exceptions/{exception_id}/audit
```

### Reconciliation / Control

```text
GET    /api/reconciliation/current
POST   /api/reconciliation/run
```

### Benchmark

```text
GET    /api/benchmark/report
```

The exact request/response schemas are available through Swagger.

---

## 🚀 Quick Start

### 1. Prerequisites

Install:

- Python 3.10+
- Node.js 18+
- npm
- A Supabase project
- OpenAI API access for real AI investigation

### 2. Clone the Repository

```bash
git clone https://github.com/mayurii-26/FinTrace-ai-financial-control.git

cd FinTrace-ai-financial-control
```

### 3. Backend Setup

Open PowerShell:

```powershell
cd backend
```

Create and activate the virtual environment:

```powershell
python -m venv venv

.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

### 4. Configure Backend Environment

Create:

```
backend/.env
```

Example:

```env
APP_ENV=local
APP_NAME=FinTrace
API_PREFIX=/api
LOG_LEVEL=INFO

DATABASE_URL=YOUR_SUPABASE_POSTGRES_CONNECTION_STRING

SYNTHETIC_RECORD_COUNT=600
SYNTHETIC_SEED=42

LLM_PROVIDER=openai
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-4o-mini

RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_MODE=test
```

> **Important:** Never commit `.env`. The repository already contains `.gitignore` rules for environment secrets.

### 5. Start the Backend

From the backend directory:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Backend:

```
http://127.0.0.1:8000
```

Swagger:

```
http://127.0.0.1:8000/docs
```

### 6. Frontend Setup

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Create:

```
frontend/.env
```

Configure the public Supabase frontend values:

```env
VITE_SUPABASE_URL=YOUR_SUPABASE_URL
VITE_SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY
```

Start the frontend:

```bash
npm run dev
```

Open:

```
http://localhost:5173
```

---

## 🌱 Seed 600 Evaluation Records

### ⚠️ Important for Evaluators

FinTrace is designed around a reproducible **600-record evaluation dataset**.

Before running the demo or benchmark, seed the database.

### Recommended Command

With the backend running, execute:

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:8000/api/seed?count=600&seed=42&force=true"
```

This creates a fresh deterministic dataset using:

```
Records: 600
Seed:    42
Force:   true
```

### Alternative: curl

```bash
curl -X POST "http://127.0.0.1:8000/api/seed?count=600&seed=42&force=true"
```

### Alternative: PowerShell WebRequest

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://127.0.0.1:8000/api/seed?count=600&seed=42&force=true"
```

### Why `force=true`?

Use `force=true` when you want to reset the existing synthetic dataset and generate a fresh evaluation batch.

This is especially useful when an evaluator runs the project more than once.

For a normal repeat run without resetting the dataset, use:

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:8000/api/seed?count=600&seed=42&force=false"
```

### Verify the Dataset

After seeding, open:

```
http://127.0.0.1:8000/docs
```

and inspect the available reconciliation and benchmark endpoints.

The Control Center should reflect the newly generated evaluation batch.

The benchmark is calculated from the records actually stored in the database.

### Recommended Evaluation Sequence

For a clean evaluator run:

```
1. Start Backend
       ↓
2. Start Frontend
       ↓
3. Seed 600 Records
       ↓
4. Open FinTrace Control Center
       ↓
5. Run / View Reconciliation
       ↓
6. Review Exceptions
       ↓
7. Investigate an Exception with AI
       ↓
8. Perform Controller Action
       ↓
9. Run Verification
       ↓
10. Review Audit Trail
       ↓
11. Run Benchmark
```

---

## 🧪 Run the Benchmark

Once the 600 records are seeded:

```powershell
Invoke-RestMethod `
  -Method GET `
  -Uri "http://127.0.0.1:8000/api/benchmark/report"
```

The benchmark reports the actual measured:

- Precision
- Recall
- F1
- Match Rate
- Throughput
- Financial Exposure
- Unresolved Exceptions

### 🧪 Run Tests

From the project root:

```bash
python -m pytest backend/tests/ -v
```

The project includes tests covering:

- Database persistence
- Financial calculations
- Control detection
- Benchmark generation
- Investigation flow
- Verification loop
- Supabase configuration
- AI provider behavior
- Razorpay integration layer

The exact test count may change as the project evolves.

---

## 🎬 Judge Demo Flow

The recommended demonstration focuses on the complete closed loop.

### 0:00 – 0:20 — Introduce the Problem

Show the landing page.

Say:

> "Financial transactions don't end when a payment succeeds. FinTrace reconstructs the complete financial lifecycle and verifies whether the final financial state is correct."

### 0:20 – 0:45 — Show the 600-Record Batch

Open the Control Center.

Show:

- Records processed
- Exceptions
- Match rate
- Financial exposure
- Detection quality
- Priority exceptions

Emphasize that the metrics are generated from the seeded dataset.

### 0:45 – 1:20 — Open the Highest-Priority Exception

Select an exception with significant financial exposure.

Show:

```text
Exception
Severity
Exposure
Status
```

### 1:20 – 1:50 — Show Financial Lifecycle Trace

Walk through:

```
ORDER
 ↓
PAYMENT
 ↓
FEE / TAX
 ↓
EXPECTED SETTLEMENT
 ↓
ACTUAL SETTLEMENT
 ↓
BANK CREDIT
```

Point to the exact stage marked **BREAK**.

### 1:50 – 2:30 — Run AI Investigation

Trigger: **Investigate**

Show:

- AI tool execution
- Retrieved evidence
- Root cause
- Confidence
- Recommendation
- Human review requirement

The key message:

> "The AI does not guess. It retrieves financial evidence through read-only tools and produces a structured recommendation."

### 2:30 – 3:00 — Controller Action

Show:

```
APPROVE
REJECT
ESCALATE
```

Perform the appropriate synthetic controller action.

### 3:00 – 3:30 — Verify

Run verification.

Show:

```
Before Exposure
       ↓
Action
       ↓
After Exposure
       ↓
VERIFIED
```

This demonstrates that FinTrace closes the loop instead of simply generating an explanation.

### 3:30 – 4:00 — Audit Trail

Open the audit timeline.

Show:

```
Detection
 ↓
Investigation
 ↓
Tool Calls
 ↓
AI Conclusion
 ↓
Controller Action
 ↓
Verification
```

### 4:00 – 4:30 — Close with the Differentiator

End with:

> "FinTrace doesn't just find financial exceptions. It traces them, explains them with evidence, prioritizes their monetary impact, keeps humans in control, and verifies that the financial state is actually corrected."

---

## 📁 Project Structure

```text
FinTrace-ai-financial-control/
│
├── backend/
│   │
│   ├── app/
│   │   ├── agent/
│   │   │   ├── agent.py
│   │   │   ├── provider.py
│   │   │   ├── prompts.py
│   │   │   ├── schemas.py
│   │   │   └── tools.py
│   │   │
│   │   ├── data/
│   │   │   └── seeder.py
│   │   │
│   │   ├── finance/
│   │   │   ├── lifecycle_trace.py
│   │   │   └── ...
│   │   │
│   │   ├── models/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   │
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   │
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── context/
│   │   ├── lib/
│   │   └── pages/
│   │
│   ├── package.json
│   └── vite.config.ts
│
├── .gitignore
└── README.md
```

### 🧠 Design Principles

**Principle 1 — Deterministic Finance**

Financial arithmetic belongs to the deterministic control engine.

```
Money → Decimal
Control → Rules
Verification → Deterministic
```

**Principle 2 — AI for Investigation**

AI is used where reasoning adds value:

- Evidence retrieval
- Context synthesis
- Root-cause analysis
- Recommendation
- Confidence assessment

**Principle 3 — Human Accountability**

AI recommends. The controller decides.

**Principle 4 — Evidence Before Explanation**

The AI must retrieve evidence before making a financial conclusion.

**Principle 5 — Confidence Must Matter**

Low-confidence AI output should not be treated as a high-confidence financial decision.

**Principle 6 — Verification Over Assumption**

A correction is successful only after the financial controls are rerun.

---

## 🔮 Future Extensions

FinTrace's architecture can be extended toward production finance operations with:

### Real-time Event Ingestion

Connect payment, settlement and banking events through streaming infrastructure.

### Continuous Controls Monitoring

Run financial controls continuously instead of in batch mode.

### Advanced Financial Forecasting

Add cash-position and liquidity forecasting based on verified settlement obligations.

### Policy Intelligence

Connect internal finance policies and contracts to investigation workflows.

### Role-Based Approval Workflows

Add granular finance-controller, auditor and operator permissions.

### Production Razorpay Workflows

Extend Test Mode integrations to controlled production workflows with appropriate approval, authentication and operational safeguards.

### Cross-Merchant Control Monitoring

Support multiple merchant accounts and consolidated finance-control dashboards.

---

## 🏆 Why FinTrace Fits Track 04

FinTrace directly addresses the core requirement of an AI Finance Controller:

```
50+ Financial Records
        ↓
Deterministic Financial Controls
        ↓
Measured Detection Quality
        ↓
Exception Prioritization
        ↓
AI Investigation
        ↓
Human Controller Action
        ↓
Verified Resolution
```

The system is designed to demonstrate both sides of finance automation:

**Throughput**
Process a large synthetic financial batch efficiently.

**Accuracy**
Evaluate detections against generated ground truth.

**Intelligence**
Use AI to investigate exceptions using real database evidence.

**Control**
Keep consequential decisions with the human controller.

**Verification**
Rerun the financial controls to prove whether the issue was resolved.

### ⚡ Final Architecture Principle

```
                    FINTRACE

        ┌───────────────────────────┐
        │     DETERMINISTIC         │
        │     FINANCIAL CONTROL     │
        │                           │
        │  Detect • Calculate       │
        │  Quantify • Verify        │
        └─────────────┬─────────────┘
                      │
                      ▼
        ┌───────────────────────────┐
        │       PROBABILISTIC       │
        │       AI INTELLIGENCE     │
        │                           │
        │  Investigate • Explain    │
        │  Recommend • Prioritize   │
        └─────────────┬─────────────┘
                      │
                      ▼
        ┌───────────────────────────┐
        │      HUMAN CONTROLLER     │
        │                           │
        │  Approve • Reject         │
        │  Escalate                 │
        └─────────────┬─────────────┘
                      │
                      ▼
        ┌───────────────────────────┐
        │        VERIFICATION       │
        │                           │
        │   Rerun → Measure → Prove │
        └───────────────────────────┘
```

**FinTrace — From financial exception to verified resolution.**

---

🏆 **Built for Razorpay Buildathon 2026**
**Track 04 — AI Finance Controller**

**FinTrace**
*AI Financial Control & Exception Intelligence*
