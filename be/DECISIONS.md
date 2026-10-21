# Checkout and Rewards Service — Engineering Decisions

## 1. Overview

This project implements a checkout and rewards service using Python, FastAPI, SQLAlchemy, and SQLite.

The service supports product listing, cart management, checkout, order retrieval, milestone-based reward coupon generation, coupon redemption, and an administrative summary report.

The main engineering priority is preserving business invariants when requests are retried, checkout attempts overlap, inventory is limited, or coupon redemption fails.

No real payment processing is performed.

## 2. Core Invariants

The implementation is designed to maintain these invariants:

1. Inventory must never become negative.
2. A cart can produce at most one order.
3. Retrying a checkout with the same idempotency key and equivalent request must not create another order or deduct inventory again.
4. Reusing an idempotency key for a different cart or coupon request must be rejected.
5. An order must preserve the product name, unit price, quantity, and line total used at checkout.
6. A coupon can be redeemed by at most one successful order.
7. Failed checkout attempts must not permanently deduct inventory or consume a coupon.
8. The order's gross amount, discount, and net amount must be stored as integer minor currency units.
9. The net amount must never be negative.
10. A rewards milestone must not generate duplicate coupons.
11. Administrative reporting must not mutate orders, inventory, or coupons.

Database constraints provide additional protection for unique order-per-cart relationships, idempotency keys, coupon codes, coupon milestones, and nonnegative inventory and monetary values.

## 3. Material Design Decisions

### Decision 1: SQLite for persistence

**Chosen:** SQLite with SQLAlchemy.

**Alternatives considered:** An in-memory Python store or a networked relational database such as PostgreSQL.

SQLite provides persistent storage, transactional operations, database constraints, and straightforward local setup without requiring a separate database server. It is suitable for this assignment and allows concurrent requests to be tested against a shared database.

An in-memory Python store would require custom synchronization and would lose state on process restart. A networked database would be more suitable for a multi-instance production service but would increase setup requirements for this time-boxed assignment.

**Trade-off:** SQLite serializes writes and is not the preferred database for a high-write, horizontally scaled checkout service.

### Decision 2: Price and availability are validated at checkout

**Chosen:** The current product price and inventory are read when checkout is processed. The order stores a snapshot of the product name, unit price, quantity, and line total.

**Alternative considered:** Locking a product price and inventory reservation when an item is first added to the cart.

The chosen approach avoids holding inventory reservations for abandoned carts and ensures the order reflects the price used by the checkout transaction. Cart totals may change when product prices change before checkout.

Inventory availability is checked and deducted as part of the checkout transaction. If sufficient stock is unavailable, checkout fails and its database changes are rolled back.

**Trade-off:** The cart does not guarantee a price or reserve stock before checkout. A client should refresh the cart to display current prices.

### Decision 3: Integer minor units for money

**Chosen:** Prices and order amounts are represented as integers in minor currency units. For example, 79900 represents 799.00 in a currency with 100 minor units per major unit.

**Alternative considered:** Binary floating-point values or decimal values stored directly in the database.

Integer arithmetic avoids binary floating-point rounding errors. The API and documentation must make the minor-unit representation explicit.

Coupon discounts use half-up rounding to the nearest minor unit:

`discount = (gross × discount_percent + 50) // 100`

The discount is capped at the gross amount, and the net amount is calculated as gross minus discount.

**Trade-off:** Clients must format minor-unit values for display. This representation assumes a currency with 100 minor units per major unit; supporting currencies with different scales would require currency-aware configuration.

### Decision 4: Transactional checkout and inventory protection

**Chosen:** Checkout runs its database operations in a single transaction. SQLite uses `BEGIN IMMEDIATE` to acquire the write transaction before the checkout reads and changes relevant state. Inventory is deducted with a conditional update that requires sufficient stock.

Order creation, order-item snapshots, cart status changes, inventory deductions, coupon redemption, and the idempotency record are committed together.

**Alternative considered:** Reading inventory and deducting it later without a transaction or conditional update.

The alternative creates a race in which two checkouts could both observe the same stock and oversell it.

If any operation fails, the transaction is rolled back. Database constraints and conditional updates provide additional safeguards.

**Trade-off:** SQLite serializes writers, which limits write concurrency. A production system with substantial checkout traffic should use a database and transaction strategy designed for concurrent workloads, such as PostgreSQL with appropriate row locking and conditional updates.

### Decision 5: Idempotency keys for checkout retries

**Chosen:** Checkout requires an `Idempotency-Key` header. The service persists the key, cart ID, normalized coupon code, and resulting order ID.

A retry using the same key and equivalent cart/coupon request returns the existing order. Reusing the key for a different cart or coupon request returns a conflict.

The unique database constraint on the idempotency key protects against duplicate records.

**Alternative considered:** Relying only on cart status to reject repeat checkout attempts.

Cart status prevents another order from being created for an already checked-out cart, but by itself it does not provide a reliable way to return the original result of a retried request.

**Trade-off:** Idempotency records require retention and operational policies in a production service. The current implementation does not define a cleanup policy.

### Decision 6: Milestone-based coupon generation

**Chosen:** Rewards configuration defines the required number of successful orders per milestone and the coupon discount percentage. A successful order is an order with status `PLACED`.

An administrator can request coupon generation. The service checks the number of successful orders and generates a coupon for the earliest eligible milestone that does not already have one.

A unique constraint on the milestone prevents duplicate coupons for the same milestone.

**Alternative considered:** Automatically creating a coupon during every checkout that reaches a milestone.

The chosen approach keeps coupon generation as an explicit administrative operation, as required by the assignment.

**Trade-off:** A milestone can be reached before an administrator requests generation. Until generation succeeds, its coupon is not available for redemption.

### Decision 7: Single-use coupons and checkout rollback

**Chosen:** A coupon is eligible only if it exists and has not already been redeemed. Redemption is performed using a conditional database update inside the checkout transaction.

The coupon redemption timestamp and order creation are committed together. If checkout fails, redemption is rolled back.

**Alternative considered:** Marking a coupon redeemed before attempting checkout.

That approach could permanently consume a coupon when inventory validation or order creation fails.

**Trade-off:** The current coupon model represents a generated coupon as either available or redeemed. Expiration, revocation, customer ownership, and coupon-specific eligibility restrictions are outside the current scope.

### Decision 8: Admin operations without authentication

**Chosen:** Administrative endpoints are clearly grouped under `/admin/`. Authentication was not implemented because the assignment explicitly states that authentication is not required.

**Alternative considered:** Implementing an authentication and role-based authorization system.

That would add scope beyond the assignment's required checkout and rewards invariants.

**Security limitation:** The `/admin/` prefix does not provide access control. These endpoints must not be exposed to untrusted users in a production deployment without authentication, authorization, and appropriate operational controls.

### Decision 9: Read-only summary reporting

**Chosen:** The administrative summary report derives totals from persisted orders, order items, and coupons. Revenue and product quantities are calculated from successful `PLACED` orders. Coupon availability is calculated as generated coupons minus redeemed coupons.

**Alternative considered:** Maintaining independent report counters updated by checkout.

Independent counters could drift if a transaction failed or an update path was missed. Deriving the report from persisted records avoids that class of inconsistency.

**Trade-off:** Aggregation queries can become expensive as data grows. Production reporting may need indexes, pagination for product details, caching, or a separate analytics pipeline.

## 4. API and Error Handling

The API is implemented with FastAPI and request/response schemas. Service-level business failures use structured HTTP errors with a `detail` message.

The service distinguishes cases such as:

- Missing cart or order: not found.
- Invalid request fields or coupon code: validation error.
- Empty or already checked-out cart: conflict.
- Insufficient inventory: conflict.
- Already-redeemed coupon: conflict.
- Idempotency key reused for a different request: conflict.
- Rewards configuration missing or milestone not reached: conflict.

FastAPI validation handles invalid request shapes and field constraints. The API documentation is available through FastAPI's generated OpenAPI interface.

No payment gateway is called. A successful checkout represents order placement, not a completed financial transaction.

## 5. Testing Strategy

The automated tests cover the following areas:

- Successful checkout and inventory deduction.
- Idempotent checkout retries.
- Rollback after failed checkout.
- Order retrieval and unknown-order handling.
- Concurrent checkout attempts against limited stock.
- Coupon generation before and after a milestone.
- Avoiding duplicate milestone coupons.
- Coupon discount calculation and redemption.
- Invalid and previously redeemed coupons.
- Retrying checkout with the same coupon and idempotency key.
- Summary reporting for an empty database and a successful order.

The tests use isolated temporary SQLite databases so they do not depend on the developer's local checkout database.

The latest recorded test run passed all 17 tests. One dependency deprecation warning was reported by the test client stack; it was not a test failure.

## 6. Multi-Instance and Production Considerations

The current implementation is intended for a local assignment environment and uses SQLite transaction semantics.

Before production deployment, the following changes should be evaluated:

1. Move to a managed relational database such as PostgreSQL for concurrent, multi-instance workloads.
2. Verify transaction isolation and locking behavior under the expected deployment topology.
3. Add authentication and role-based authorization for administrative operations.
4. Configure production secrets, database credentials, migrations, backups, and monitoring.
5. Define idempotency-key retention and request replay policies.
6. Add request rate limits, structured logging, metrics, and alerting.
7. Add database indexes based on measured query plans and workload.
8. Add API-level pagination and filtering where report size warrants it.
9. Define coupon expiration and administrative revocation policies if required by the business.
10. Add load and fault-injection tests for database contention and service restarts.

The current tests demonstrate behavior against the configured SQLite test database. They do not establish production throughput or multi-instance guarantees for a different database deployment.

## 7. Implemented and Deferred Scope

### Implemented

- Product listing and seeded sample inventory.
- Cart creation and item management.
- Checkout and order retrieval.
- Integer-based monetary calculations.
- Transactional inventory deduction.
- Checkout idempotency.
- Order-item snapshots.
- Milestone-based coupon generation.
- Single-use coupon redemption.
- Rewards configuration.
- Administrative summary reporting.
- Automated checkout, concurrency, coupon, and report tests.

### Deferred

- Real payment processing.
- Authentication and authorization.
- Multi-currency support.
- Coupon expiration and revocation.
- Inventory reservation before checkout.
- Production deployment and multi-instance database validation.
- Load testing and performance optimization.
- Idempotency-record retention and cleanup.
- Advanced report filtering and pagination.

Deferred items are not represented as implemented functionality.

## 8. AI Assistance and Engineering Ownership

AI assistance was used to support implementation planning, review edge cases, troubleshoot test failures, and improve test coverage.

An example of corrective iteration was the coupon test setup: the test helper returned a cart ID and already created cart items. An initial test edit incorrectly treated the return value as a cart object and attempted to insert duplicate items. The test setup was corrected to use the returned ID and rely on the helper's existing item creation behavior.

AI-generated suggestions were checked against the repository's actual helper behavior and test results rather than accepted without verification.

All implementation decisions and code must be understood and reviewed by the candidate before submission. Any additional AI-generated code should be tested and reconciled with the actual repository state.

## 9. If Two Additional Hours Were Available

The highest-priority improvements would be:

1. Add a concurrent coupon-redemption test proving that only one competing checkout can redeem a coupon.
2. Add a test proving a failed checkout leaves a coupon available for a later successful attempt.
3. Add API contract tests for reward configuration, coupon generation, and report response schemas.
4. Add database migration support instead of relying only on table creation at startup.
5. Review and complete README documentation with endpoint examples, request/response formats, and error cases.
6. Run the complete test suite and manually verify the documented API flows.
7. Review the final diff, remove unused imports, and verify that generated database files and virtual-environment artifacts are excluded from version control.

## 10. Time Spent

The following is an approximate breakdown; time was not tracked precisely.

- Environment setup and project structure: 1 hour
- Backend implementation: 4 hours
- Automated testing and concurrency verification: 2 hours
- README and design decisions documentation: 1.5 hours
- Final review and cleanup: 0.5 hour

**Approximate total: 9 hours**

These estimates are approximate and reflect the work performed on this assignment.
