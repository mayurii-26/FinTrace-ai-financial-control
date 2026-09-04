# System Architecture — FinTrace

**Track 04 — AI Finance Controller**
**Razorpay AI Buildathon 2026**

---

## 1. Core Architectural Principle

> **"Deterministic finance. Probabilistic intelligence."**

FinTrace separates financial truth from AI reasoning.

The deterministic control engine is the authoritative source for:

- Financial calculations
- Lifecycle validation
- Exception detection
- Monetary exposure
- Verification

The AI investigation layer is responsible for:

- Evidence retrieval
- Root-cause analysis
- Investigation reasoning
- Confidence assessment
- Recommendations

The controller remains responsible for consequential actions.

| Layer | Responsibility | What it cannot do |
|---|---|---|
| **Deterministic Control Engine** | Financial calculations, lifecycle validation, exception detection, exposure calculation and verification | Delegate financial truth to the LLM |
| **AI Investigation Layer** | Retrieve evidence, analyze exceptions, identify probable root cause and recommend action | Modify financial records or perform authoritative calculations |
| **Controller** | Approve, reject or escalate an exception | Bypass deterministic verification |
| **Audit Layer** | Record detection, investigation, actions, tool calls and verification | Remove or alter historical audit events |

---

## 2. System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                         FINTRACE FRONTEND                              │
│                                                                          │
│              React + TypeScript + Vite + Tailwind CSS                  │
│                                                                          │
│   Control Center │ Exceptions │ Investigation │ Audit Trail │ Auth      │
└───────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 │ REST / JSON
                                 │ JWT Bearer Token
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                                │
│                                                                          │
│   API Routes │ Authentication │ Investigation │ Actions │ Verification  │
└──────────────┬──────────────────────┬──────────────────────┬───────────┘
               │                      │                      │
               ▼                      ▼                      ▼
┌──────────────────────┐   ┌──────────────────────┐   ┌─────────────────┐
│ DETERMINISTIC        │   │ AI INVESTIGATION     │   │ AUDIT / CONTROL │
│ CONTROL ENGINE        │   │ LAYER                │   │ STATE           │
│                       │   │                      │   │                 │
│ • Lifecycle checks    │   │ • OpenAI             │   │ • Exceptions    │
│ • Financial checks    │   │ • Read-only tools    │   │ • Investigations│
│ • Detection           │   │ • Evidence retrieval │   │ • Actions       │
│ • Exposure            │   │ • Root cause         │   │ • Verification  │
│ • Verification        │   │ • Confidence         │   │ • Audit logs    │
└──────────┬────────────┘   └──────────┬───────────┘   └────────┬────────┘
           │                           │                          │
           └───────────────────────────┼──────────────────────────┘
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │      SUPABASE          │
                          │      PostgreSQL        │
                          │                        │
                          │ Orders                 │
                          │ Payments               │
                          │ Refunds                │
                          │ Settlements            │
                          │ Bank Entries           │
                          │ Exceptions             │
                          │ Investigations         │
                          │ Audit Logs             │
                          └────────────────────────┘

                               Optional Integration
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │    RAZORPAY TEST MODE  │
                          │                        │
                          │    Python SDK          │
                          └────────────────────────┘
```

---

## 3. Financial Lifecycle Model

FinTrace models a transaction as a connected financial lifecycle rather than an isolated payment.

```text
ORDER
  │
  ▼
PAYMENT
  │
  ├──────────────► REFUND
  │
  ▼
FEE / TAX
  │
  ▼
EXPECTED SETTLEMENT
  │
  ▼
ACTUAL SETTLEMENT
  │
  ▼
BANK CREDIT
```

The system reconstructs this chain for each transaction.

Each lifecycle stage is evaluated independently.

```text
VALID
   │
   ├── Expected relationship exists
   │
WARNING
   │
   ├── Relationship exists but timing/value is suspicious
   │
BREAK
   │
   ├── Financial inconsistency detected
   │
MISSING
   │
   └── Expected downstream event does not exist
```

This allows FinTrace to answer:

> **Where exactly did the financial lifecycle break?**

---

## 4. Core Operating Loop

FinTrace closes the finance-control loop:

```text
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
   ↓
AUDIT
```

### Step 1 — INGEST

Financial lifecycle records are generated as controlled synthetic data and stored in the relational database.

The dataset contains connected records across:

- Orders
- Payments
- Refunds
- Fees / Taxes
- Settlements
- Bank Entries

A deterministic seed allows the same benchmark dataset to be reproduced.

### Step 2 — CONTROL

The deterministic control engine evaluates relationships between financial entities.

All monetary calculations use Python `Decimal` arithmetic.

The LLM is never treated as the source of financial truth.

```text
Financial Amount
      ↓
Python Decimal
      ↓
Deterministic Control
      ↓
Authoritative Result
```

### Step 3 — DETECT

Control failures are converted into structured exceptions.

FinTrace currently models scenarios such as:

- `HEALTHY`
- `SETTLEMENT_AMOUNT_DISCREPANCY`
- `REFUND_CLOSURE_FAILURE`
- `DUPLICATE_FINANCIAL_EVENT`
- `ORPHAN_FINANCIAL_EVENT`
- `SETTLEMENT_TIMING_ANOMALY`
- `MISSING_DOWNSTREAM_EVENT`

Each exception contains structured information such as:

- Exception ID
- Transaction reference
- Exception type
- Severity
- Exposure
- Status
- Detection evidence

### Step 4 — QUANTIFY

Every detected exception is assigned a monetary exposure.

The exposure is calculated by deterministic finance logic.

This enables prioritization based on financial impact.

```text
Exception A                    Exception B
₹1,00,000 Exposure       VS    ₹100 Exposure
1 Exception                    10 Exceptions
```

FinTrace prioritizes the issue that represents greater financial risk rather than simply counting exceptions.

---

## 5. Deterministic Control Engine

The control engine is implemented independently from the AI layer.

Its responsibilities include:

```text
┌───────────────────────────────────────┐
│       DETERMINISTIC CONTROL ENGINE     │
├───────────────────────────────────────┤
│                                        │
│ Lifecycle Reconstruction               │
│ Financial Consistency                  │
│ Exception Detection                    │
│ Exposure Calculation                   │
│ Severity Classification                │
│ Verification                           │
│                                        │
│ Python Decimal = Financial Truth       │
└───────────────────────────────────────┘
```

The engine does not ask the LLM whether an amount is correct.

Instead:

```text
DATABASE
   ↓
CONTROL RULE
   ↓
DECIMAL CALCULATION
   ↓
DETERMINISTIC RESULT
```

The AI receives the result and investigates the reason behind it.

---

## 6. AI Investigation Architecture

FinTrace uses AI only after a deterministic exception has been detected.

```text
Exception
    ↓
Investigation Request
    ↓
AI Investigator
    ↓
Read-Only Database Tools
    ↓
Evidence Collection
    ↓
Root Cause Analysis
    ↓
Confidence Assessment
    ↓
Recommendation
```

The AI cannot directly access the database.

It interacts through controlled read-only tools.

### Investigation Tools

- `get_transaction()`
- `get_payment_details()`
- `get_refund_details()`
- `get_settlement_details()`
- `get_bank_entry()`
- `get_financial_timeline()`

These tools retrieve actual records from the database.

The tool execution trace becomes part of the investigation evidence.

---

## 7. Evidence-Backed Investigation

The AI must ground its conclusion in retrieved evidence.

The investigation output contains:

- Exception Type
- Severity
- Root Cause
- Evidence
- Missing Evidence
- Confidence
- Recommendation
- Recommended Action
- Human Review Requirement

The system explicitly supports insufficient evidence.

```text
Evidence Available
        ↓
AI Analysis
        ↓
Confidence
        ↓
Recommendation
```

If required evidence is missing, the AI should not invent a root cause.

---

## 8. Confidence-Aware Decision Policy

FinTrace uses explicit confidence thresholds.

```text
┌─────────────────────────────────────────────┐
│              CONFIDENCE POLICY               │
├─────────────────────────────────────────────┤
│                                               │
│  ≥ 0.90                                      │
│  HIGH CONFIDENCE                             │
│  Clear evidence-backed recommendation        │
│                                               │
│  0.70 – < 0.90                               │
│  CONTROLLER VERIFICATION                     │
│  Human verification required                 │
│                                               │
│  < 0.70                                      │
│  INSUFFICIENT EVIDENCE                       │
│  Manual investigation required                │
│                                               │
└─────────────────────────────────────────────┘
```

| Confidence Range | Classification | Outcome |
|---|---|---|
| ≥ 0.90 | High Confidence | Clear evidence-backed recommendation |
| 0.70 – < 0.90 | Controller Verification | Human verification required |
| < 0.70 | Insufficient Evidence | Manual investigation required |

Confidence does not change the underlying financial calculation.

It only controls how much trust can be placed in the AI recommendation.

---

## 9. Human-in-the-Loop Control

FinTrace is designed as a controller assistant.

The AI can:

```text
INVESTIGATE
    ↓
RETRIEVE EVIDENCE
    ↓
IDENTIFY PROBABLE ROOT CAUSE
    ↓
RECOMMEND ACTION
```

The controller can then explicitly choose:

- `APPROVE`
- `REJECT`
- `ESCALATE`

The AI does not independently mutate financial records.

---

## 10. Closed-Loop Verification

FinTrace does not consider an exception resolved merely because the AI recommends a correction.

After a controller action, the deterministic control is executed again.

```text
BEFORE EXPOSURE
        ↓
CONTROLLER ACTION
        ↓
RERUN DETERMINISTIC CONTROL
        ↓
AFTER EXPOSURE
        ↓
VERIFIED / FAILED
```

An exception becomes:

> **VERIFIED**

only when deterministic verification confirms that the financial inconsistency has been resolved.

This creates measurable closure instead of an AI-generated claim of resolution.

---

## 11. Audit Trail

Every important control event is recorded.

```text
DETECTION
   ↓
INVESTIGATION STARTED
   ↓
TOOL CALLS
   ↓
AI CONCLUSION
   ↓
CONTROLLER ACTION
   ↓
VERIFICATION
```

The audit trail captures:

- Exception activity
- Investigation activity
- Evidence retrieval
- AI conclusion
- Confidence
- Controller action
- Verification result

This provides traceability from the original financial record to the final control outcome.

---

## 12. Database Architecture

FinTrace uses a relational PostgreSQL database through Supabase.

**orders**

```text
id
amount
status
customer_id
created_at
```

**payments**

```text
id
order_id
amount
status
method
created_at
```

**refunds**

```text
id
payment_id
amount
status
reason
created_at
```

**settlements**

```text
id
payment_id
amount
status
settled_at
```

**bank_entries**

```text
id
settlement_id
amount
reference
credited_at
```

**exceptions**

```text
id
transaction_id
exception_type
severity
exposure
status
root_cause
```

**investigations**

```text
id
exception_id
confidence
recommendation
evidence
missing_evidence
created_at
```

**audit_logs**

```text
id
exception_id
event_type
details
created_at
```

The actual SQLAlchemy models define the relationships and persistence layer.

---

## 13. Authentication and API Security

FinTrace uses Supabase Authentication for user sessions.

```text
User
 ↓
Supabase Authentication
 ↓
JWT Access Token
 ↓
Frontend API Request
 ↓
Authorization: Bearer <token>
 ↓
FastAPI Backend
```

The frontend does not contain backend secrets.

Environment-specific credentials are stored through environment variables.

**Frontend**

- Supabase URL
- Supabase Anon Key

**Backend**

- Database credentials
- OpenAI API Key
- Razorpay credentials

Secrets are excluded from version control through `.gitignore`.

---

## 14. OpenAI Integration

OpenAI is used as the probabilistic investigation layer.

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=<backend secret>
OPENAI_MODEL=gpt-4o-mini
```

The provider architecture supports a mock fallback for development and resilience.

```text
AI Investigation Request
          ↓
     OpenAI Provider
          │
          ├── Available → OpenAI Tool Calling
          │
          └── Unavailable → Mock Investigation
```

The fallback still uses the same investigation output structure and database tools.

This prevents the application from becoming unusable when the external AI service is unavailable.

---

## 15. Razorpay Integration

FinTrace is designed with Razorpay integration support through the Razorpay Python SDK and Test Mode.

The integration layer is isolated from the deterministic control engine.

```text
FinTrace
   │
   └── Razorpay Client
            │
            └── Test Mode
```

The core benchmark does not depend on live financial transactions.

This ensures that evaluation remains deterministic and safe.

---

## 16. Benchmark Architecture

FinTrace generates a controlled synthetic dataset with known ground truth.

```text
Synthetic Generator
        ↓
Financial Lifecycle Records
        ↓
Known Scenario Labels
        ↓
Deterministic Control Engine
        ↓
Predicted Exceptions
        ↓
Compare With Ground Truth
        ↓
Benchmark Metrics
```

The benchmark reports measurable metrics such as:

- Total records
- Healthy records
- Detected exceptions
- Match rate
- Precision
- Recall
- F1 score
- Throughput
- Total financial value
- Total financial exposure
- Resolved exceptions
- Unresolved exceptions

Throughput is measured using runtime measurement rather than a hardcoded value.

---

## 17. Performance Measurement

The system measures control-engine performance using Python timing instrumentation.

```text
Start Timer
    ↓
Process Batch
    ↓
Run Deterministic Controls
    ↓
Stop Timer
    ↓
records / elapsed_seconds
    ↓
Measured Throughput
```

The benchmark therefore reports actual execution results for the environment in which it is run.

No benchmark value should be hardcoded into evaluation output.

---

## 18. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React + TypeScript + Vite |
| Styling | Tailwind CSS |
| Charts | Recharts |
| Icons | Lucide |
| Backend | FastAPI |
| ORM | SQLAlchemy |
| Validation | Pydantic |
| Database | PostgreSQL / Supabase |
| AI | OpenAI API |
| Financial Arithmetic | Python Decimal |
| Synthetic Data | Faker + Python |
| Statistical Advisory | scikit-learn |
| Payment Integration | Razorpay Python SDK |
| Authentication | Supabase Auth |
| Testing | Pytest |

---

## 19. Design Principles

### Principle 1 — Deterministic Financial Truth

> **LLM ≠ Financial Calculator**

All authoritative financial calculations are deterministic.

### Principle 2 — Evidence Before Explanation

```text
Evidence
   ↓
Reasoning
   ↓
Recommendation
```

Not:

```text
LLM Guess
   ↓
Financial Decision
```

### Principle 3 — Exposure Over Exception Count

> **Financial Impact > Raw Exception Count**

### Principle 4 — Human Control

```text
AI Recommendation
       ↓
Controller Decision
       ↓
Verification
```

### Principle 5 — Verification Over Assertion

> **"AI says fixed" ≠ "Financial control passed"**

Only deterministic verification can close an exception.

---

## 20. End-to-End Architecture

```text
                    FINTRACE
                       │
                       ▼
                 INGEST DATA
                       │
                       ▼
              FINANCIAL LIFECYCLE
                       │
                       ▼
            DETERMINISTIC CONTROLS
                       │
                       ▼
                EXCEPTIONS
                       │
                       ▼
             EXPOSURE PRIORITY
                       │
                       ▼
              AI INVESTIGATION
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
        Evidence             Confidence
             │                   │
             └─────────┬─────────┘
                       ▼
                RECOMMENDATION
                       │
                       ▼
              CONTROLLER ACTION
                       │
                       ▼
            DETERMINISTIC VERIFY
                       │
              ┌────────┴────────┐
              ▼                 ▼
          VERIFIED            FAILED
              │                 │
              └────────┬────────┘
                       ▼
                  AUDIT TRAIL
```

---

## 21. Final Architectural Statement

FinTrace is not simply a reconciliation dashboard and not an autonomous financial agent.

It is a closed-loop AI financial control system that combines:

- Deterministic Financial Controls
- Financial Lifecycle Tracing
- Exposure Prioritization
- Evidence-Backed AI Investigation
- Human Controller Oversight
- Deterministic Verification
- Complete Auditability

FinTrace answers not only whether a payment succeeded, but whether the entire financial lifecycle remained correct through final bank credit.
