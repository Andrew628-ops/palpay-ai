# PalPay AI

**Intelligent conditional payments powered by Gemini AI, human review, and PayPal Sandbox.**

PalPay AI is a hackathon MVP for managing payments tied to agreed conditions. An operator creates a SmartPay rule, evidence is submitted for review, and Gemini assesses the submitted description against the condition. When evidence is uncertain, a human reviewer can request more information or reject it. An authorized operator can approve a qualifying rule and initiate a **PayPal Sandbox** payout, while the application records payment updates and review history.

> **Sandbox demonstration only.** PalPay AI does not handle production money, provide escrow, or independently prove that off-platform work has been completed. AI recommendations are advisory and must not be treated as verified proof.

## What PalPay AI does

- **Conditional payment rules:** Create a recipient, amount, currency, description, and release condition.
- **Evidence submission and resubmission:** Keep each submission as a separate record so earlier evidence and analysis remain available.
- **Gemini AI review:** Assess the latest submission and recommend `APPROVE`, `REJECT`, or further review.
- **Human oversight:** Record `REQUEST_MORE_EVIDENCE` or `REJECT` decisions with an explanation, submission reference, reviewer label, and timestamp.
- **Separate payment authorization:** AI review alone does not initiate a payout. A protected approval step must precede payment.
- **PayPal Sandbox payout integration:** Create and track test payouts with duplicate-request protection.
- **Webhook and reconciliation support:** Verify PayPal webhook signatures, store events, and reconcile saved payout records.
- **Audit and reporting:** View submission history, human decision history, review queue, payment history, and summary analytics.
- **Responsive interface:** Dashboard, Payments, AI Reviews, and Settings pages, with mobile-friendly navigation and a payment progress timeline.

## How it works

```text
Create SmartPay rule
        |
        v
Submit evidence
        |
        v
Gemini reviews latest submission
        |
        +-- APPROVE --> Await human payment approval
        |                      |
        |                      v
        |                Authorized approval
        |                      |
        |                      v
        |                PayPal Sandbox payout
        |                      |
        |                      v
        |                PayPal status reconciliation
        |
        +-- NEEDS_REVIEW --> Human evidence review
        |                      |
        |                      +-- Request more evidence --> Resubmit --> Gemini review
        |                      |
        |                      +-- Reject --> Review cycle closed
        |
        +-- REJECT --> Evidence can be revised under the demo workflow
```

**Important distinction:** A human *evidence* decision is not a payment approval. Requesting more evidence or rejecting evidence does not send money.

### Core statuses

| Status | Meaning |
| --- | --- |
| `WAITING_FOR_CONDITION` | Rule created; evidence not yet submitted |
| `CONDITION_SUBMITTED` | Submission ready for Gemini review |
| `NEEDS_REVIEW` | Gemini requires human attention |
| `EVIDENCE_REQUESTED` | Human reviewer requested additional evidence |
| `AI_REJECTED` | Gemini rejected the submitted evidence |
| `HUMAN_REJECTED` | Human reviewer closed the review cycle |
| `AWAITING_USER_APPROVAL` | AI recommended approval; operator approval needed |
| `USER_APPROVED` | Authorized approval recorded; payout not yet sent |
| `PAYOUT_REQUESTED` / `PAYOUT_SUBMITTED` | Sandbox payout initiation or processing |
| `PAYOUT_UNKNOWN` | Payout outcome uncertain; reconcile before retrying |
| `PAID` | Payout confirmed through the PayPal status workflow |
| `PAYOUT_FAILED` / `PAYOUT_REFUNDED` / `PAYOUT_RETURNED` | Non-success or reversal outcomes |

## Technology stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI, Pydantic |
| Persistence | SQLAlchemy, SQLite (local MVP) |
| AI review | Gemini integration |
| Payments | PayPal Payouts API **Sandbox** |
| Webhook development | PayPal webhook verification; optional ngrok tunnel |
| Tests | pytest, FastAPI TestClient, isolated SQLite databases, mocks |

## Repository overview

```text
palpay-ai/
├── app/
│   ├── main.py                    # FastAPI application / router registration
│   ├── database.py                # Database engine and sessions
│   ├── models.py                  # Rule, submission, payout, webhook, audit models
│   ├── schemas.py                 # Pydantic request/response models
│   ├── routers/
│   │   ├── rules.py
│   │   ├── ai_review.py
│   │   ├── human_review.py
│   │   ├── review_queue.py
│   │   ├── submission_history.py
│   │   ├── payouts.py
│   │   ├── payment_history.py
│   │   └── webhooks.py
│   └── services/
│       ├── ai.py                  # Gemini review service
│       ├── paypal.py              # PayPal API client
│       ├── payout_reconciliation.py
│       └── webhook_processing.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/             # Analytics, reviews, history, payouts, timeline
│   └── package.json
├── tests/                         # Backend unit, API and workflow tests
├── .env                           # Local secrets (do not commit)
└── README.md
```

*This is a guide to the main modules, not a complete file listing. Your checkout may contain additional scripts, styles, and tests.*

## Local setup

### Prerequisites

- Python 3.12 or a compatible version supported by the project's dependencies
- Node.js and npm (the frontend is built with Vite)
- PayPal **Sandbox** developer credentials and Sandbox receiving account
- Gemini API access for real AI reviews
- Optional: ngrok or another HTTPS tunnel for receiving PayPal webhooks locally

### 1. Backend

From the repository root:

```bash
python -m venv venv
source venv/bin/activate           # Linux / macOS
python -m pip install -r requirements.txt
```

> If your checkout does not include `requirements.txt`, install dependencies using the project's existing Python dependency setup before starting the server. Do not assume the list above is complete.

Create a local `.env` file in the repository root. Use **your own Sandbox credentials**; never commit them or paste them into an issue or screenshot.

```dotenv
# Replace with an absolute path to your local database file.
DATABASE_URL=sqlite:////absolute/path/to/palpay-ai/palpay.db

# Demo-only shared operator secret; use a long, random value.
APPROVAL_TOKEN=replace-with-private-random-demo-token

PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=your-sandbox-client-id
PAYPAL_CLIENT_SECRET=your-sandbox-client-secret
PAYPAL_SANDBOX_RECEIVER_EMAIL=your-sandbox-receiver@example.com
PAYPAL_WEBHOOK_ID=your-sandbox-webhook-id

# Configure the Gemini API key using the exact variable
# expected by app/services/ai.py in your checkout.
```

The local project has used an absolute SQLite database URL to avoid accidentally creating or reading a different database when commands run from another working directory.

Start FastAPI:

```bash
uvicorn app.main:app --reload --port 8000
```

API documentation: **http://127.0.0.1:8000/docs**

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the address printed by Vite (typically **http://localhost:5173**). The frontend's `/api` requests must reach the FastAPI backend; check `frontend/vite.config.js` if you change the backend host or port.

Build for a production-style frontend check:

```bash
npm run build
```

### 3. Optional: local PayPal webhooks

Start an HTTPS tunnel to your locally running backend, for example:

```bash
ngrok http 8000
```

Register the HTTPS callback URL ending in `/api/webhooks/paypal` in your **PayPal Sandbox** webhook configuration. Ensure `PAYPAL_WEBHOOK_ID` corresponds to that webhook. Configure the project's retry worker separately if you are using it; the HTTP server and the worker are not the same process.

**Never switch `PAYPAL_BASE_URL` to the live PayPal API for this demo.** The payout implementation intentionally enforces the Sandbox endpoint.

## Main API endpoints

These paths reflect the implemented FastAPI router structure. Use Swagger at `/docs` as the final reference for exact request bodies and required headers.

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/api/rules/smartpay` | Create a SmartPay rule |
| `GET` | `/api/rules/smartpay/{rule_id}` | Retrieve a rule |
| `POST` | `/api/rules/smartpay/{rule_id}/submit` | Submit initial evidence |
| `POST` | `/api/rules/smartpay/{rule_id}/resubmit` | Submit improved evidence |
| `GET` | `/api/rules/smartpay/{rule_id}/submissions` | Read submission and AI-review history |
| `POST` | `/api/rules/smartpay/{rule_id}/ai-review` | Review latest evidence with Gemini |
| `POST` | `/api/rules/smartpay/{rule_id}/approve` | Record protected payment approval |
| `GET` | `/api/reviews/queue` | List rules needing attention |
| `POST` | `/api/reviews/{rule_id}/human-decision` | Request more evidence or reject |
| `GET` | `/api/reviews/{rule_id}/human-decisions` | Read human decision audit history |
| `GET` | `/api/rules/smartpay/{rule_id}/payout-preview` | Review proposed Sandbox payout |
| `POST` | `/api/rules/smartpay/{rule_id}/pay` | Initiate authorized Sandbox payout |
| `GET` | `/api/rules/smartpay/{rule_id}/payment-status` | Read recorded payout status |
| `POST` | `/api/rules/smartpay/{rule_id}/payment-status/refresh` | Reconcile an existing payout |
| `GET` | `/api/payments/history` | List payout records |
| `GET` | `/api/payments/summary` | Load dashboard analytics |
| `POST` | `/api/webhooks/paypal` | Receive and verify PayPal events |

Protected demo operator endpoints use the `x-approval-token` request header. PayPal webhooks instead require PayPal's signature headers and verification flow. Do not store a shared approval token in frontend source code or `localStorage`.

## Testing

From the repository root, with the Python environment active:

```bash
python -m pytest -q
```

The test suite exercises major flows including evidence resubmission, AI-review selection, authorization, human decisions, audit history, payout safety, and webhook processing. The development tests use temporary SQLite databases and mocks for external calls; a passing suite does **not** mean live PayPal or Gemini behavior has been fully verified.

Frontend build check:

```bash
cd frontend
npm run build
```

## Security model and known limitations

### Implemented for the Sandbox MVP

- Sandbox-only payout URL check and explicit receiver confirmation
- Operator token checks on sensitive demo endpoints
- Conditional status updates and a unique payout record per rule to reduce duplicate-payout risk
- Verified PayPal webhooks stored by unique event ID
- Webhook processing claims, retries, and transaction rollback on failed reconciliation
- Matching of payout identity, recipient, currency, and amount during reconciliation
- Protection against overwriting a recorded refund/return with an outdated success status
- Separate AI, human evidence-review, payment-approval, and payout steps

### Before any production or real-money use

- Replace the shared operator token with real authentication, authorization, and ownership/role checks. The current `sandbox-operator` audit label does not identify a person.
- Add stronger concurrency controls across *different* webhook events and payout reconciliation requests, plus explicit handling for permanently stale events.
- Add proper migrations, deployment configuration, HTTPS, secure secret management, and operational monitoring.
- Thoroughly validate external evidence sources: the AI may analyze a submitted description without actually opening or verifying a URL, screenshot, or deliverable.
- Complete threat modeling, end-to-end tests against the correct Sandbox environment, and payment-provider compliance review.
- Do not describe this prototype as escrow, payment guarantees, or a production financial service.

## Project status

**PalPay AI is a working, tested hackathon Sandbox MVP** with an end-to-end demonstration of evidence review, human oversight, resubmission, and previously confirmed PayPal Sandbox payouts. It is **not production-ready**.