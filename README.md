# Ecommerce Checkout & Rewards API

A backend service for an ecommerce store that supports product browsing, cart management, checkout, discount coupon redemption, and administrative rewards reporting.

## Features

- Create and manage shopping carts.
- Add, update, and remove cart items.
- Checkout with inventory validation and coupon discount validation.
- Idempotent checkout requests to prevent duplicate orders on retries.
- Generate discount coupons when eligible order milestones are reached.
- Prevent duplicate coupon redemption and overselling during concurrent checkouts.
- Admin endpoints for rewards configuration, coupon generation, and sales summaries.

## Tech Stack

- Python
- FastAPI
- SQLAlchemy
- SQLite
- Pytest

## Project Structure

- `be/` — Backend application, APIs, business logic, and tests.
- `be/README.md` — Backend setup instructions and API documentation.
- `be/DECISIONS.md` — Design decisions, trade-offs, and implementation considerations.
- `fe/` — Optional React and TypeScript enrollment review workbench, separate from the ecommerce assignment.

## Setup and Run

The backend setup and run instructions are maintained in [`be/README.md`](be/README.md). Follow that document to install dependencies, configure the environment, start the API server, and access the API documentation.

## Run Tests

From the repository root:

```bash
cd be
python -m pytest -v
```

## Design Decisions

The ecommerce backend's design decisions, including checkout consistency, idempotency, inventory concurrency, coupon validation, money handling, and production considerations, are documented in [`be/DECISIONS.md`](be/DECISIONS.md).

## Verification

Backend automated tests: 17 passed in the latest recorded test run.

## Scope Notes

This repository also contains a separate frontend assignment in `fe/`. The ecommerce checkout and rewards implementation is in `be/`.

## Assignment Deliverables

- Working backend APIs for cart management, checkout, coupon validation, and administrative reporting.
- Automated tests for core business logic.
- Setup instructions and API documentation.
- Root-level `DECISIONS.md` documenting design decisions, trade-offs, concurrency, idempotency, money rounding, errors, deferred work, production scaling, AI usage, and possible next steps.
- Meaningful Git history showing implementation progression.
- GitHub repository link for submission.

The backend is the required part of the ecommerce assignment. The `fe/` directory contains a separate frontend assignment and is maintained independently.

## Known Scope Limitations

- Admin endpoints do not include authentication; authorization was outside the implemented assignment scope.
- SQLite is used for this implementation. Production deployment across multiple application instances would require reviewing database locking, migrations, and concurrency behavior for the chosen production database.

## Submission

Repository: [https://github.com/neustackapp/assignment](https://github.com/neustackapp/assignment)

Before submission, run the backend tests and review the final Git status and commit history. Report only verification results that have actually been run.
