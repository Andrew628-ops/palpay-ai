# PalPay AI — The Intelligent Payment Agent

**Conditional payments powered by Gemini AI, human oversight, and PayPal Sandbox.**

PalPay AI is a full-stack hackathon prototype that connects an agreed payment condition to an evidence-review workflow. A user creates a SmartPay agreement, submits evidence, and receives a recommendation from Google Gemini. The application keeps AI recommendations separate from human payment authorization, and an authorized operator can initiate and track **PayPal Sandbox** payouts.

> **Sandbox prototype — not a real-money payment or escrow service.** Gemini analyzes the evidence submitted to the application; its recommendations are advisory, not independent verification that off-platform work was completed. `APPROVE` does **not** mean money was sent. A payment is recorded as `PAID` only following the application's PayPal status-confirmation workflow.

## Live demo and source code

- **Hosted application:** [Open the live application](https://palpay-ai-demo.onrender.com/)
- **Source code:** [GitHub repository](https://github.com/Andrew628-ops/palpay-ai)
- **Demo video:** [Watch the demo video](https://youtu.be/4-c8gfiBzzY)

### What works in the hosted demo?

The hosted Render deployment uses **FastAPI + React + PostgreSQL**. Its restricted public demo configuration enables test agreement creation and evidence submission with fictional data. AI review is protected by an operator token. Operator-only payment authorization, PayPal payout execution, and payment-status refresh remain blocked in the public environment by `DEMO_READ_ONLY=true` and the deployment middleware. The AI-review endpoint also requires an operator token.

**Want to test the complete, real Sandbox workflow?** Clone the repository and configure your **own Gemini API key, PayPal Sandbox credentials, and operator token**. The local application uses the actual human-authorization and PayPal Sandbox payout logic; it does **not** replace those operations with a fake payment simulation.

> **Public demo limitation:** The prototype does not yet implement user accounts or agreement ownership isolation. Use fictional names, test evidence, and Sandbox accounts only. Do not submit private recipient information. Public write endpoints need rate limiting and stronger access controls before wider use.

## Key features

- **SmartPay agreements:** Define a recipient, amount, currency, description, and release condition.
- **Evidence and resubmission:** Submit or revise evidence while preserving submission history.
- **Gemini AI evaluation:** Receive `APPROVE`, `REJECT`, or `NEEDS_REVIEW` recommendations for the latest evidence.
- **Human evidence review:** Request more evidence or reject a review case with an auditable decision.
- **Separate payment authorization:** An authorized operator must approve an eligible agreement before payout.
- **PayPal Payouts API (Sandbox):** Initiate test payouts using the PayPal developer environment.
- **Payment reconciliation:** Track payout status and handle uncertain outcomes without blindly retrying.
- **Webhook processing:** Verify and store PayPal webhook events for payment-state updates.
- **Dashboard and audit trail:** Review agreements, submissions, decisions, payout history, and analytics.

## End-to-end workflow

```text
Create a SmartPay agreement
          |
          v
     Submit evidence
          |
          v
    Gemini AI review
          |
          +-- APPROVE ----------------------+
          |                                 |
          |                     Await authorized approval
          |                                 |
          |                                 v
          |                      Human payment approval
          |                                 |
          |                                 v
          |                       PayPal Sandbox payout
          |                                 |
          |                                 v
          |                     PayPal status verification
          |
          +-- NEEDS_REVIEW --> Human evidence review
          |                         |
          |                         +-- Request more evidence --> Resubmit
          |                         |
          |                         +-- Reject evidence
          |
          +-- REJECT --> Revise evidence if workflow permits
```

**Human evidence review and human payment approval are different actions.** A favorable AI recommendation is never, by itself, permission to transfer funds.

### Agreement and payout statuses

| Status | Meaning |
| --- | --- |
| `WAITING_FOR_CONDITION` | Agreement exists; evidence has not been submitted |
| `CONDITION_SUBMITTED` | Evidence is ready for Gemini review |
| `NEEDS_REVIEW` | AI requested human attention |
| `EVIDENCE_REQUESTED` | Reviewer requested another submission |
| `AI_REJECTED` | AI rejected the submitted evidence |
| `HUMAN_REJECTED` | Human reviewer closed the review cycle |
| `AWAITING_USER_APPROVAL` | AI recommends approval; payment authorization is still required |
| `USER_APPROVED` | Authorized approval recorded; payout has not yet been sent |
| `PAYOUT_REQUESTED` / `PAYOUT_SUBMITTED` | Sandbox payout requested or submitted |
| `PAYOUT_UNKNOWN` | Outcome is uncertain; reconcile before any retry |
| `PAID` | Confirmed by the PayPal status workflow |
| `PAYOUT_FAILED` / `PAYOUT_REFUNDED` / `PAYOUT_RETURNED` | Non-success or reversal status |

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI, Pydantic |
| ORM and database | SQLAlchemy; SQLite for local development, PostgreSQL for hosted deployment |
| AI | Google Gemini API |
| Payments | PayPal Payouts API **Sandbox** |
| Webhooks | PayPal webhook signature verification; optional ngrok for local testing |
| Deployment | Docker and Render |
| Testing | pytest, FastAPI TestClient, isolated test databases, mocked external calls |

## Project structure

```text
palpay-ai/
├── app/
│   ├── main.py                    # FastAPI app, routers and frontend serving
│   ├── database.py                # SQLAlchemy engine and sessions
│   ├── models.py                  # Database models
│   ├── schemas.py                 # Request/response schemas
│   ├── routers/                   # Agreements, reviews, payouts, history, webhooks
│   └── services/                  # Gemini, PayPal and reconciliation logic
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   └── package.json
├── tests/                        # Backend and workflow tests
├── requirements.txt
├── Dockerfile
├── .dockerignore
└── README.md
```

## Run locally with your own Sandbox

### Requirements

- Python 3.12 (or another version compatible with the pinned dependencies)
- Node.js and npm
- Google Gemini API key
- PayPal developer **Sandbox** app credentials and a Sandbox receiving account
- Optional: ngrok or another HTTPS tunnel for PayPal webhook testing

### 1. Clone and install the backend

```bash
git clone https://github.com/Andrew628-ops/palpay-ai.git
cd palpay-ai
python -m venv venv
source venv/bin/activate             # Linux / macOS
# Windows PowerShell: .\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file in the repository root. **Use only credentials from your own developer accounts.** Delete or comment out the `DATABASE_URL` line to use the local SQLite default configured in `app/database.py`, or replace it with your own valid database URL.

```dotenv
# Optional local database override:
# DATABASE_URL=sqlite:////absolute/path/to/palpay-ai/palpay.db
# Generate a strong value with: python -c "import secrets; print(secrets.token_urlsafe(32))"
APPROVAL_TOKEN=replace-with-your-private-random-token
GEMINI_API_KEY=your-gemini-api-key
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID=your-sandbox-client-id
PAYPAL_CLIENT_SECRET=your-sandbox-client-secret
PAYPAL_SANDBOX_RECEIVER_EMAIL=your-sandbox-receiver@example.com
PAYPAL_WEBHOOK_ID=your-sandbox-webhook-id
# Full local Sandbox workflow. Do not use this setting on an unrestricted public service.
DEMO_READ_ONLY=false
```

`PAYPAL_WEBHOOK_ID` is required for the corresponding webhook verification flow; if you have not registered a webhook yet, configure it when you test webhooks.

**Never commit `.env`, database files, private tokens, or PayPal/Gemini credentials to Git.** Never use PayPal's live-money API URL with this prototype.

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

FastAPI API docs: http://127.0.0.1:8000/docs

### 2. Install and run the frontend

Open a second terminal:

```bash
cd frontend             # Run from the repository root
npm install
npm run dev
```

Visit the local URL printed by Vite (often http://localhost:5173). The Vite `/api` proxy must point to your FastAPI server; check `frontend/vite.config.js` if you change the backend address.

### 3. Test a complete Sandbox agreement

1. Create a SmartPay agreement with a **fictional** recipient and a small Sandbox amount.
2. Submit evidence satisfying the specified condition.
3. Request a Gemini review and inspect its recommendation and explanation.
4. If the recommendation permits it, use the **private operator token** to authorize payment.
5. Confirm the Sandbox receiver and submit a PayPal Sandbox payout.
6. Use payout status refresh or verified webhooks to reconcile the transaction.
7. Inspect the payment timeline and audit history.

The operator token is a shared demo secret, not a real user login. Do not distribute it to public visitors or embed it in frontend source code.

### 4. Optional local webhooks

```bash
ngrok http 8000
```

Register the HTTPS callback ending in `/api/webhooks/paypal` in your **PayPal Sandbox** developer app. Set `PAYPAL_WEBHOOK_ID` to the ID of that webhook. The optional retry worker is separate from the FastAPI HTTP server.

## Deployment on Render

The repository includes a multistage `Dockerfile` that builds the Vite frontend and serves its production files through FastAPI. The hosted service runs against PostgreSQL using `DATABASE_URL`.

For a restricted public demo:

- Connect the repository to a Render **Docker Web Service**.
- Use a Render PostgreSQL database in the **same region**, then set `DATABASE_URL` to its private internal database URL.
- Configure secrets in Render's **Environment** settings, not in source control.
- Set `DEMO_READ_ONLY=true` to keep the protected payment actions disabled in the public demo. The project's middleware permits only the specific interactive routes explicitly allowed by the current deployment configuration.
- Keep genuine payout authorization, payout execution, and reconciliation restricted to a trusted operator environment.

**Important:** A publicly accessible app without proper user authentication is not suitable for storing sensitive agreement information. Free hosting resources can also have availability and data-retention limits; check the provider's current terms before relying on the service.

## Main API endpoints

The exact request bodies and required headers are documented in FastAPI Swagger UI (`/docs`).

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/rules/smartpay` | Create agreement |
| `GET` | `/api/rules/smartpay/{rule_id}` | Get agreement |
| `POST` | `/api/rules/smartpay/{rule_id}/submit` | Submit evidence |
| `POST` | `/api/rules/smartpay/{rule_id}/resubmit` | Resubmit evidence |
| `GET` | `/api/rules/smartpay/{rule_id}/submissions` | View submission and AI history |
| `POST` | `/api/rules/smartpay/{rule_id}/ai-review` | Request Gemini review |
| `POST` | `/api/rules/smartpay/{rule_id}/approve` | Protected payment authorization |
| `GET` | `/api/reviews/queue` | Review queue |
| `POST` | `/api/reviews/{rule_id}/human-decision` | Record human evidence decision |
| `GET` | `/api/reviews/{rule_id}/human-decisions` | Human-review history |
| `GET` | `/api/rules/smartpay/{rule_id}/payout-preview` | Preview Sandbox payout |
| `POST` | `/api/rules/smartpay/{rule_id}/pay` | Protected Sandbox payout |
| `GET` | `/api/rules/smartpay/{rule_id}/payment-status` | Get recorded payment status |
| `POST` | `/api/rules/smartpay/{rule_id}/payment-status/refresh` | Reconcile existing payout |
| `GET` | `/api/payments/history` | Payment history |
| `GET` | `/api/payments/summary` | Summary analytics |
| `POST` | `/api/webhooks/paypal` | Verify and receive PayPal events |

Sensitive operator routes use the `x-approval-token` request header; PayPal webhook verification instead uses PayPal's signature headers. **Do not publish the approval token.**

## Tests and validation

From the repository root:

```bash
python -m pytest -q
cd frontend
npm run build
```

The backend test suite covers agreement state changes, evidence resubmission, AI-review selection, human decision history, payment authorization, payout safety, and webhook processing. Some tests use isolated SQLite databases and mocked external services. Passing local tests does **not** replace live Sandbox integration testing.

During development, a small PayPal **Sandbox** payout was successfully confirmed using the status-refresh flow. This demonstrates integration in the developer environment; it is **not** a real-money transaction and does not imply that every public user can execute payouts.

## Security and known limitations

### Protections included in the prototype

- PayPal Sandbox-only payout configuration and receiver confirmation.
- A separate approval step, independent of Gemini's recommendation.
- Shared operator token checks on sensitive endpoints.
- A payout record and request identifiers intended to reduce duplicate-payment risk.
- Signature-verified PayPal webhooks, stored events, and reconciliation checks.
- Evidence, AI-review, human-decision, and payment audit history.
- Restricted payment operations in the hosted public demo.

### Not yet production-ready

- No real user authentication, per-agreement ownership, or role-based authorization.
- Publicly exposed creation and submission routes need stronger rate limits, request-size controls, abuse protection, and privacy isolation.
- A shared operator token is **not** an adequate production authorization model.
- Gemini recommendations can be mistaken; submitted evidence is not independently verified just because Gemini says `APPROVE`.
- Robust database migrations, observability, webhook concurrency controls, and provider compliance checks are still needed.
- This is not escrow, a payment guarantee, or a system for moving real money.

## Project status

**PalPay AI is a deployed, working hackathon Sandbox MVP**, with a React/FastAPI interface, Gemini evidence-review workflow, human oversight, and genuine PayPal **Sandbox** integration. The hosted demo is intentionally restricted; developers who configure their own test credentials can explore the full workflow locally.

Built for the **Build What's Next with PayPal and AI** hackathon.

## License

Released under the [MIT License](LICENSE). See the repository `LICENSE` file for the full terms.