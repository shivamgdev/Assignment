#Full-Stack Engineer

## Build a Reliable Checkout and Rewards Service

You are building the backend for an ecommerce store. Customers create carts, add products, and check out. The store rewards purchasing activity by making a discount coupon available after every *n*th successfully placed order.

The basic endpoints are straightforward. The challenge is making the system behave predictably when requests are retried, multiple customers check out concurrently, inventory changes, or two operations compete for the same coupon.

We are evaluating how you reason about those situations—not how quickly you can generate CRUD code.

## Timebox

Please spend **no more than 4–6 hours** on the assignment.

We do not expect every production concern to be implemented. Prioritize the risks you consider most important, implement a coherent solution, and document what you intentionally deferred in `DECISIONS.md`.

## Business Requirements

### Products and inventory

- A product has an ID, name, current unit price, and available inventory.
- Seed at least five products. Include at least one product with limited inventory.
- A cart may contain multiple products and quantities.
- Invalid products or quantities must not silently enter a cart.
- The system must not sell more inventory than is available.

### Carts

- A client can create a cart, add an item, change its quantity, remove an item, and view the cart.
- Return useful prices and totals when viewing a cart.
- A cart must not be checked out more than once.
- Decide and document what happens when product price or availability changes after an item was added but before checkout.

### Checkout and orders

- Checkout validates the cart and, if successful, creates an order.
- Clients may retry a checkout request because they timed out or did not receive the response. A retry must not accidentally create another order or charge inventory twice.
- Concurrent checkout attempts must not oversell inventory.
- An order must retain enough information to explain what the customer purchased and how its total was calculated, even if product data later changes.
- Calculate money without floating-point rounding errors.
- Return errors that are distinguishable and useful to an API client.

No real payment integration is required. Treat successful checkout as payment success, or introduce a small payment abstraction/fake if it supports your design. Explain the choice.

### Discount coupons

- Configure the system with values `n` and `x`. For example, when `n = 5` and `x = 10`, every fifth successfully placed order makes one coupon for 10% off available.
- An administrator can request coupon generation.
- A coupon is generated only if the configured order milestone has been reached and a coupon has not already been generated for that milestone.
- A valid coupon may be supplied at checkout.
- A coupon can be redeemed only once.
- A coupon must not be lost or consumed by a checkout that ultimately fails.
- A coupon must not be redeemed successfully by two concurrent checkouts.
- Discount calculations must be deterministic and must never make an order total negative.

You will need to decide some coupon semantics that are not specified here. Make defensible choices and record them.

### Administration and reporting

Provide administrator operations to:

1. Generate a coupon when an unrewarded milestone is eligible.
2. Return a summary containing:
   - successfully purchased quantity by product;
   - gross revenue before discounts;
   - total discounts granted;
   - net revenue;
   - coupons generated, available, and redeemed; and
   - total successfully placed orders.

The report should reconcile with the orders and coupons returned by your system. Repeated report requests must not mutate state.

## API Design

Design the HTTP API you believe best represents the domain. At minimum, it must support:

- cart creation and retrieval;
- adding, updating, and removing cart items;
- checkout with an optional coupon;
- retrieving an order;
- administrator coupon generation; and
- administrator reporting.

Document each endpoint, request, response, expected status code, and important error case. You may provide an OpenAPI document, an API client collection, executable examples, or clear README documentation.

Authentication and authorization do not need to be implemented. Clearly identify which operations you treat as administrative.

## Persistence and Concurrency

You may use a database, an embedded database, or an in-memory implementation.

An in-memory implementation is acceptable only if it still demonstrates how you preserve the required invariants when requests overlap. Explain how the design would change with multiple application instances and a production database.

We may exercise the service with concurrent requests and repeated requests. Tests that only call each endpoint once in a happy-path sequence will not be sufficient.

## Required Deliverables

### 1. Working service

- Source code in the stack of your choice
- Repeatable setup and run instructions
- Seed data or migrations required to evaluate the service
- No dependency on private services or credentials

### 2. Automated tests

Include focused tests for the business rules and failure modes you consider most important. We value a small number of meaningful tests over high superficial coverage.

At least one test must exercise competing or repeated operations—not merely sequential happy paths.

### 3. `DECISIONS.md`

This is a required and heavily weighted part of the submission. Include:

- the system invariants you identified;
- ambiguities you found and the semantics you selected;
- at least five material design decisions and alternatives considered;
- your transaction, concurrency, and idempotency strategy;
- money and rounding rules;
- error-model choices;
- what you implemented versus intentionally deferred;
- how the design would evolve for multiple service instances and production scale;
- how you used AI tools, including an example where you corrected, rejected, or materially redirected AI output; and
- what you would examine first if given another two hours.

For each material decision, a useful structure is:

```markdown
## Decision: [Title]

**Context:** What correctness or design problem were you solving?

**Options considered:** What credible alternatives did you consider?

**Choice:** What did you choose?

**Why:** What trade-offs, constraints, or failure modes drove the decision?

**Consequences:** What becomes easier, harder, or deferred as a result?
```

### 4. Repository history

Commit your work in meaningful increments. We do not grade the number of commits, but the history should help us understand how the solution developed.

## AI Use

You are encouraged to use ChatGPT, Codex, Claude, Copilot, or other AI tools. Using AI is not a shortcut we penalize; using generated code without validating its behavior is.

You are responsible for every line submitted. In the follow-up discussion, we may ask you to:

- explain an invariant and show where it is enforced;
- predict behavior under a concurrent or repeated request;
- identify a weakness in your implementation;
- change one business rule; or
- debug a failing scenario with us.

Do not include private AI transcripts. A concise account of how AI affected your approach belongs in `DECISIONS.md`.

## Evaluation

We will evaluate:

1. **Correctness and invariants** — orders, inventory, coupons, and reporting remain consistent.
2. **Reasoning and judgment** — ambiguities and trade-offs are recognized and resolved deliberately.
3. **Failure behavior** — retries, conflicts, validation failures, and concurrent operations have coherent outcomes.
4. **Domain and API design** — responsibilities, state transitions, and error contracts are understandable.
5. **Testing** — tests target meaningful risks and can expose incorrect implementations.
6. **Code quality** — the implementation is focused, readable, and proportionate to the timebox.
7. **Ownership of AI-assisted work** — the candidate can critique, explain, and modify what they submitted.

Frontend work is optional and will not compensate for an unreliable backend. If you add a frontend, keep it small and use it to demonstrate the backend behavior.

## Submission

Share a public or access-granted Git repository containing:

- source code;
- setup and run instructions;
- API documentation or executable examples;
- automated tests; and
- `DECISIONS.md`.

State the approximate time spent. If something is incomplete, tell us directly and explain how you would finish it.

Good luck—we are looking forward to discussing your reasoning.
## Implementation Guide

### Overview

The backend uses Python, FastAPI, SQLAlchemy, and SQLite. It supports product listing, cart management, checkout, order retrieval, configurable rewards, coupon generation and redemption, and an administrative summary report.

No external payment provider is integrated. A successful checkout represents successful order placement.

### Prerequisites

- Python 3.11 or later
- pip

### Setup and Run

Open a terminal in the `be` directory.

Create and activate a virtual environment on Windows:

```text
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install dependencies:

```text
python -m pip install -r requirements.txt
```

Start the API:

```text
python -m uvicorn app.main:app --reload
```

The default SQLite database is stored in the backend directory. Sample products are seeded when the product table is empty.

Interactive API documentation: http://127.0.0.1:8000/docs

### Automated Tests

Run the tests from the `be` directory:

```text
python -m pytest -v
```

Tests use isolated temporary SQLite databases.

### API Reference

| Method | Endpoint | Purpose | Success |
|---|---|---|---:|
| GET | `/health` | Health check | 200 |
| GET | `/products` | List products | 200 |
| POST | `/carts` | Create a cart | 201 |
| GET | `/carts/{cart_id}` | Retrieve a cart and totals | 200 |
| POST | `/carts/{cart_id}/items` | Add a product and quantity | 200 |
| PUT | `/carts/{cart_id}/items/{product_id}` | Update item quantity | 200 |
| DELETE | `/carts/{cart_id}/items/{product_id}` | Remove a cart item | 200 |
| POST | `/carts/{cart_id}/checkout` | Check out a cart | 201 |
| GET | `/orders/{order_id}` | Retrieve an order | 200 |
| GET | `/admin/rewards/config` | Retrieve rewards configuration | 200 |
| PUT | `/admin/rewards/config` | Update rewards configuration | 200 |
| POST | `/admin/rewards/coupons/generate` | Generate an eligible coupon | 200 |
| GET | `/admin/reports/summary` | Retrieve the summary report | 200 |

### Request and Response Contracts

All request and response bodies use JSON where applicable. Example IDs and values are illustrative. Monetary values use integer minor currency units rather than floating-point values.

**Products — `GET /products`**

Returns an array of products:

```json
[
  {
    "id": 1,
    "name": "Wireless Mouse",
    "unit_price_minor": 79900,
    "inventory": 25
  }
]
```

**Create a cart — `POST /carts`**

No request body is required. Returns `201 Created`:

```json
{
  "id": 1,
  "status": "OPEN"
}
```

**Retrieve a cart — `GET /carts/{cart_id}`**

Returns the cart, its items, and the current total:

```json
{
  "id": 1,
  "status": "OPEN",
  "items": [
    {
      "product_id": 1,
      "product_name": "Wireless Mouse",
      "quantity": 2,
      "unit_price_minor": 79900,
      "line_total_minor": 159800
    }
  ],
  "total_minor": 159800
}
```

**Add an item — `POST /carts/{cart_id}/items`**

Request:

```json
{
  "product_id": 1,
  "quantity": 2
}
```

Returns `200 OK` with the updated cart response.

**Update an item — `PUT /carts/{cart_id}/items/{product_id}`**

Request:

```json
{
  "quantity": 3
}
```

Returns `200 OK` with the updated cart response.

**Remove an item — `DELETE /carts/{cart_id}/items/{product_id}`**

No request body is required. Returns `200 OK` with the updated cart response.

**Checkout — `POST /carts/{cart_id}/checkout`**

The `Idempotency-Key` header is required. An optional `coupon_code` query parameter can be supplied.

Example request:

```text
POST /carts/1/checkout?coupon_code=REWARD-EXAMPLE
Idempotency-Key: checkout-request-001
```

Returns `201 Created` for a new checkout:

```json
{
  "id": 1,
  "cart_id": 1,
  "status": "PLACED",
  "gross_total_minor": 159800,
  "discount_minor": 15980,
  "net_total_minor": 143820,
  "items": [
    {
      "product_id": 1,
      "product_name": "Wireless Mouse",
      "unit_price_minor": 79900,
      "quantity": 2,
      "line_total_minor": 159800
    }
  ]
}
```

The example discount assumes a valid 10% coupon. Without a coupon, `discount_minor` is zero. Use a real generated coupon when testing coupon redemption.

A retry using the same idempotency key and the same cart and coupon returns the existing order without creating another order or deducting inventory again. Reusing a key for a different checkout request returns `409 Conflict`.

**Retrieve an order — `GET /orders/{order_id}`**

Returns `200 OK` with the order response, including purchase-time item snapshots. Returns `404 Not Found` when the order does not exist.

**Configure rewards — `PUT /admin/rewards/config`**

Request:

```json
{
  "orders_per_coupon": 5,
  "discount_percent": 10
}
```

Returns `200 OK` with the saved configuration. Both values must be positive integers; the discount percentage cannot exceed 100.

**Read rewards configuration — `GET /admin/rewards/config`**

Returns `200 OK` with the current configuration. Returns `404 Not Found` if no configuration has been set.

**Generate a coupon — `POST /admin/rewards/coupons/generate`**

No request body is required. Returns `200 OK` with a result containing `generated`, `message`, and `coupon`. The coupon may be `null` when generation does not occur. Generation requires a configured rewards rule and a reached order milestone.

Each milestone can have at most one coupon. If multiple milestones are eligible, the service generates the earliest missing milestone first.

**Summary report — `GET /admin/reports/summary`**

Returns `200 OK` with:

- `total_successful_orders`
- `gross_revenue_minor`
- `total_discounts_minor`
- `net_revenue_minor`
- `coupons_generated`
- `coupons_available`
- `coupons_redeemed`
- `products`: product ID, product name, and quantity sold

The report is read-only and uses successfully placed orders.

### Error Handling

Service-level errors use this response shape:

```json
{
  "detail": "Cart not found"
}
```

Important HTTP statuses include:

| Status | Meaning | Examples |
|---|---|---|
| 404 | Resource not found | Missing cart, product, order, or cart item |
| 409 | Conflict with current state | Empty or checked-out cart, insufficient inventory, redeemed coupon, conflicting idempotency key, or coupon milestone not reached |
| 422 | Invalid input | Invalid quantity, invalid coupon input, or invalid rewards configuration |

FastAPI request validation errors also return `422` with FastAPI's standard validation response format. Exact service error messages are returned in the `detail` field.

### Pricing, Inventory, and Coupon Rules

- Product prices and inventory are checked at checkout. Adding a product to a cart does not lock its price.
- The order stores product names, unit prices, quantities, and line totals as a purchase-time snapshot.
- Checkout uses database transactions and conditional inventory updates to help prevent overselling.
- Coupon redemption and order creation happen in the same checkout transaction. Failed checkouts do not permanently consume coupons.
- A coupon can be redeemed only once.
- Monetary calculations use integer minor units and deterministic integer rounding.

### Administration and Security

All `/admin/` endpoints are administrative operations. Authentication and authorization are not implemented because they were outside the assignment scope. These endpoints must be protected before production deployment.

### Persistence and Limitations

SQLite provides persistent storage for this assignment. Transactions, conditional updates, and database constraints help preserve checkout and coupon invariants.

The implementation has not been load-tested for production traffic or validated for multi-instance deployment. For production, evaluate PostgreSQL or another server database, authentication and authorization, database migrations, monitoring, backups, and operational retention policies.

See `DECISIONS.md` for design decisions, trade-offs, implemented and deferred scope, AI usage, and possible future improvements.