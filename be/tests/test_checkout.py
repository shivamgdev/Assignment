
import pytest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.main as main
from app.database import Base, get_db
from app.models import Cart, CartItem, Order, Product
from app.services import ServiceError, checkout_cart

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.models import Coupon, RewardsConfig

@asynccontextmanager
async def isolated_lifespan(app):
    yield


@pytest.fixture
def db_session(tmp_path):
    database_path = tmp_path / "checkout_test.db"
    test_engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    with test_session_factory() as db:
        db.add_all(
            [
                Product(
                    id=1,
                    name="Test Mouse",
                    unit_price_minor=79900,
                    inventory=5,
                ),
                Product(
                    id=2,
                    name="Test Keyboard",
                    unit_price_minor=249900,
                    inventory=0,
                ),
            ]
        )
        db.commit()
        yield db

    test_engine.dispose()


@pytest.fixture
def api_client(tmp_path):
    database_path = tmp_path / "api_checkout_test.db"
    test_engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    with test_session_factory() as db:
        db.add_all(
            [
                Product(
                    id=1,
                    name="Test Mouse",
                    unit_price_minor=79900,
                    inventory=5,
                ),
                Product(
                    id=2,
                    name="Test Keyboard",
                    unit_price_minor=249900,
                    inventory=0,
                ),
            ]
        )
        db.commit()

    def override_get_db():
        with test_session_factory() as db:
            yield db

    previous_overrides = main.app.dependency_overrides.copy()
    previous_lifespan = main.app.router.lifespan_context

    main.app.dependency_overrides[get_db] = override_get_db
    main.app.router.lifespan_context = isolated_lifespan
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        main.app.dependency_overrides.clear()
        main.app.dependency_overrides.update(previous_overrides)
        main.app.router.lifespan_context = previous_lifespan
        test_engine.dispose()


def create_cart(db, product_quantities):
    cart = Cart(status="OPEN")
    db.add(cart)
    db.flush()

    for product_id, quantity in product_quantities:
        db.add(
            CartItem(
                cart_id=cart.id,
                product_id=product_id,
                quantity=quantity,
            )
        )

    db.commit()
    return cart.id


def test_checkout_creates_order_and_deducts_inventory(db_session):
    cart_id = create_cart(db_session, [(1, 2)])

    order = checkout_cart(
        db_session,
        cart_id,
        "checkout-success-001",
    )

    product = db_session.get(Product, 1)
    cart = db_session.get(Cart, cart_id)

    assert order.status == "PLACED"
    assert order.gross_total_minor == 159800
    assert order.discount_minor == 0
    assert order.net_total_minor == 159800
    assert len(order.items) == 1
    assert order.items[0].quantity == 2
    assert order.items[0].unit_price_minor == 79900
    assert product.inventory == 3
    assert cart.status == "CHECKED_OUT"


def test_checkout_retry_returns_same_order_without_second_deduction(
    db_session,
):
    cart_id = create_cart(db_session, [(1, 2)])

    first_order = checkout_cart(
        db_session,
        cart_id,
        "checkout-retry-001",
    )
    inventory_after_first_checkout = db_session.get(Product, 1).inventory

    retry_order = checkout_cart(
        db_session,
        cart_id,
        "checkout-retry-001",
    )

    assert retry_order.id == first_order.id
    assert db_session.scalar(
        select(Order.id).where(Order.cart_id == cart_id)
    ) == first_order.id
    assert db_session.get(Product, 1).inventory == inventory_after_first_checkout
    assert inventory_after_first_checkout == 3


def test_failed_checkout_rolls_back_inventory_and_creates_no_order(
    db_session,
):
    cart_id = create_cart(db_session, [(1, 2), (2, 1)])

    with pytest.raises(ServiceError) as error:
        checkout_cart(
            db_session,
            cart_id,
            "checkout-insufficient-001",
        )

    assert error.value.status_code == 409
    assert db_session.get(Product, 1).inventory == 5
    assert db_session.get(Product, 2).inventory == 0
    assert db_session.scalar(
        select(Order.id).where(Order.cart_id == cart_id)
    ) is None
    assert db_session.get(Cart, cart_id).status == "OPEN"


def test_checkout_api_returns_order_and_allows_order_retrieval(api_client):
    cart_response = api_client.post("/carts")

    assert cart_response.status_code == 201
    cart_id = cart_response.json()["id"]

    add_response = api_client.post(
        f"/carts/{cart_id}/items",
        json={"product_id": 1, "quantity": 2},
    )

    assert add_response.status_code == 200

    checkout_response = api_client.post(
        f"/carts/{cart_id}/checkout",
        headers={"Idempotency-Key": "api-checkout-001"},
    )

    assert checkout_response.status_code == 201

    order = checkout_response.json()

    assert order["gross_total_minor"] == 159800
    assert order["net_total_minor"] == 159800

    retrieval_response = api_client.get(f"/orders/{order['id']}")

    assert retrieval_response.status_code == 200
    assert retrieval_response.json()["id"] == order["id"]


def test_checkout_api_retry_returns_same_order(api_client):
    cart_response = api_client.post("/carts")
    assert cart_response.status_code == 201

    cart_id = cart_response.json()["id"]

    add_response = api_client.post(
        f"/carts/{cart_id}/items",
        json={"product_id": 1, "quantity": 2},
    )
    assert add_response.status_code == 200

    headers = {"Idempotency-Key": "api-checkout-retry-001"}

    first_response = api_client.post(
        f"/carts/{cart_id}/checkout",
        headers=headers,
    )
    retry_response = api_client.post(
        f"/carts/{cart_id}/checkout",
        headers=headers,
    )

    assert first_response.status_code == 201
    assert retry_response.status_code == 201
    assert retry_response.json()["id"] == first_response.json()["id"]


def test_order_api_returns_404_for_unknown_order(api_client):
    response = api_client.get("/orders/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Order not found"



def test_concurrent_checkouts_cannot_oversell(tmp_path):
    database_path = tmp_path / "concurrent_checkout_test.db"
    test_engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    with test_session_factory() as db:
        db.add(
            Product(
                id=1,
                name="Limited Mouse",
                unit_price_minor=79900,
                inventory=3,
            )
        )
        db.commit()

        cart_ids = [
            create_cart(db, [(1, 2)]),
            create_cart(db, [(1, 2)]),
        ]

    barrier = Barrier(2)

    def attempt_checkout(cart_id, idempotency_key):
        with test_session_factory() as db:
            barrier.wait()

            try:
                order = checkout_cart(
                    db,
                    cart_id,
                    idempotency_key,
                )
                return ("success", order.id)
            except ServiceError as error:
                return ("error", error.status_code)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    attempt_checkout,
                    cart_ids[0],
                    "concurrent-checkout-001",
                ),
                executor.submit(
                    attempt_checkout,
                    cart_ids[1],
                    "concurrent-checkout-002",
                ),
            ]
            results = [future.result(timeout=15) for future in futures]

        assert sum(result[0] == "success" for result in results) == 1
        assert sum(result == ("error", 409) for result in results) == 1

        with test_session_factory() as db:
            product = db.get(Product, 1)
            orders = db.scalars(select(Order)).all()

            assert product.inventory == 1
            assert len(orders) == 1
    finally:
        test_engine.dispose()



def test_coupon_generation_requires_reached_milestone(db_session):
    from app.services import generate_reward_coupon

    db_session.add(
        RewardsConfig(orders_per_coupon=5, discount_percent=10)
    )
    db_session.commit()

    with pytest.raises(ServiceError) as exc:
        generate_reward_coupon(db_session)

    assert exc.value.status_code == 409
    assert db_session.scalar(select(Coupon.id)) is None


def test_coupon_generation_uses_next_missing_milestone(db_session):
    from app.services import generate_reward_coupon

    db_session.add(
        RewardsConfig(orders_per_coupon=5, discount_percent=10)
    )

    for index in range(12):
        cart = Cart(status="CHECKED_OUT")
        db_session.add(cart)
        db_session.flush()

        order = Order(
            status="PLACED",
            cart_id=cart.id,
            idempotency_key=f"milestone-test-{index}",
            gross_total_minor=1000,
            discount_minor=0,
            net_total_minor=1000,
        )
        db_session.add(order)

    db_session.add(
        Coupon(
            code="REWARD-EXISTING5",
            milestone_order_count=5,
            discount_percent=10,
        )
    )
    db_session.commit()

    result = generate_reward_coupon(db_session)

    assert result["generated"] is True
    assert result["coupon"].milestone_order_count == 10
    assert result["coupon"].discount_percent == 10


def test_coupon_generation_does_not_duplicate_generated_milestones(db_session):
    from app.services import generate_reward_coupon

    db_session.add(
        RewardsConfig(orders_per_coupon=5, discount_percent=10)
    )

    for index in range(5):
        cart = Cart(status="CHECKED_OUT")
        db_session.add(cart)
        db_session.flush()

        db_session.add(
            Order(
                status="PLACED",
                cart_id=cart.id,
                idempotency_key=f"duplicate-test-{index}",
                gross_total_minor=1000,
                discount_minor=0,
                net_total_minor=1000,
            )
        )

    db_session.add(
        Coupon(
            code="REWARD-EXISTING5",
            milestone_order_count=5,
            discount_percent=10,
        )
    )
    db_session.commit()

    result = generate_reward_coupon(db_session)

    assert result["generated"] is False
    assert result["coupon"] is None
    assert db_session.scalar(
        select(Coupon.id).where(Coupon.milestone_order_count == 5)
    ) is not None




def test_checkout_redeems_coupon_and_applies_discount(db_session):
    from app.services import checkout_cart

    coupon = Coupon(
        code="REWARD-TEST10",
        milestone_order_count=5,
        discount_percent=10,
    )
    db_session.add(coupon)
    db_session.commit()

    cart_id = create_cart(db_session, [(1, 1)])

    order = checkout_cart(
        db_session,
        cart_id,
        "coupon-checkout-001",
        "REWARD-TEST10",
    )

    db_session.refresh(coupon)

    assert order.gross_total_minor == 79900
    assert order.discount_minor == 7990
    assert order.net_total_minor == 71910
    assert order.coupon_id == coupon.id
    assert coupon.redeemed_at is not None


def test_invalid_coupon_does_not_deduct_inventory(db_session):
    from app.services import checkout_cart

    cart_id = create_cart(db_session, [(1, 1)])

    product = db_session.get(Product, 1)
    initial_inventory = product.inventory

    with pytest.raises(ServiceError) as exc:
        checkout_cart(
            db_session,
            cart_id,
            "invalid-coupon-001",
            "NOT-A-COUPON",
        )

    assert exc.value.status_code == 422
    db_session.refresh(product)
    assert product.inventory == initial_inventory
    assert db_session.scalar(select(Order.id)) is None


def test_redeemed_coupon_cannot_be_used_again(db_session):
    from app.services import checkout_cart
    from datetime import datetime, timezone

    coupon = Coupon(
        code="REWARD-USED10",
        milestone_order_count=5,
        discount_percent=10,
        redeemed_at=datetime.now(timezone.utc),
    )
    db_session.add(coupon)
    db_session.commit()

    cart_id = create_cart(db_session, [(1, 1)])

    with pytest.raises(ServiceError) as exc:
        checkout_cart(
            db_session,
            cart_id,
            "redeemed-coupon-001",
            "REWARD-USED10",
        )

    assert exc.value.status_code == 409
    assert db_session.scalar(select(Order.id)) is None


def test_checkout_retry_with_same_coupon_returns_same_order(db_session):
    from app.services import checkout_cart

    coupon = Coupon(
        code="REWARD-RETRY10",
        milestone_order_count=5,
        discount_percent=10,
    )
    db_session.add(coupon)
    db_session.commit()

    cart_id = create_cart(db_session, [(1, 1)])

    first_order = checkout_cart(
        db_session,
        cart_id,
        "coupon-retry-001",
        "REWARD-RETRY10",
    )
    second_order = checkout_cart(
        db_session,
        cart_id,
        "coupon-retry-001",
        "REWARD-RETRY10",
    )

    assert first_order.id == second_order.id
    assert first_order.discount_minor == 7990
    assert db_session.query(Order).count() == 1



def test_admin_summary_report_returns_zero_totals_initially(api_client):
    response = api_client.get("/admin/reports/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["total_successful_orders"] == 0
    assert data["gross_revenue_minor"] == 0
    assert data["total_discounts_minor"] == 0
    assert data["net_revenue_minor"] == 0
    assert data["coupons_generated"] == 0
    assert data["coupons_available"] == 0
    assert data["coupons_redeemed"] == 0
    assert data["products"] == []


def test_admin_summary_report_counts_successful_orders(api_client):
    cart_response = api_client.post("/carts")
    assert cart_response.status_code in (200, 201)
    cart_id = cart_response.json()["id"]

    item_response = api_client.post(
        f"/carts/{cart_id}/items",
        json={"product_id": 1, "quantity": 2},
    )
    assert item_response.status_code in (200, 201)

    checkout_response = api_client.post(
        f"/carts/{cart_id}/checkout",
        headers={"Idempotency-Key": "summary-report-test-001"},
    )
    assert checkout_response.status_code == 201

    response = api_client.get("/admin/reports/summary")

    assert response.status_code == 200

    data = response.json()

    assert data["total_successful_orders"] == 1
    assert data["gross_revenue_minor"] == 159800
    assert data["total_discounts_minor"] == 0
    assert data["net_revenue_minor"] == 159800
    assert len(data["products"]) == 1
    assert data["products"][0]["product_id"] == 1
    assert data["products"][0]["quantity_sold"] == 2



def test_concurrent_checkouts_cannot_redeem_coupon_twice(tmp_path):
    database_path = tmp_path / "concurrent_coupon_test.db"
    test_engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    Base.metadata.create_all(bind=test_engine)

    try:
        with test_session_factory() as db:
            db.add(
                Product(
                    id=1,
                    name="Coupon Test Mouse",
                    unit_price_minor=79900,
                    inventory=5,
                )
            )
            db.add(
                Coupon(
                    code="REWARD-CONCURRENT10",
                    milestone_order_count=5,
                    discount_percent=10,
                )
            )
            db.commit()

            cart_ids = [
                create_cart(db, [(1, 1)]),
                create_cart(db, [(1, 1)]),
            ]

        barrier = Barrier(2)

        def attempt_checkout(cart_id, idempotency_key):
            with test_session_factory() as db:
                barrier.wait()

                try:
                    order = checkout_cart(
                        db,
                        cart_id,
                        idempotency_key,
                        "REWARD-CONCURRENT10",
                    )
                    return ("success", order.id)
                except ServiceError as error:
                    return ("error", error.status_code)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    attempt_checkout,
                    cart_ids[0],
                    "concurrent-coupon-001",
                ),
                executor.submit(
                    attempt_checkout,
                    cart_ids[1],
                    "concurrent-coupon-002",
                ),
            ]
            results = [future.result(timeout=15) for future in futures]

        assert sum(result[0] == "success" for result in results) == 1
        assert sum(result == ("error", 409) for result in results) == 1

        with test_session_factory() as db:
            coupon = db.scalar(
                select(Coupon).where(
                    Coupon.code == "REWARD-CONCURRENT10"
                )
            )
            orders = db.scalars(select(Order)).all()
            product = db.get(Product, 1)

            assert coupon.redeemed_at is not None
            assert len(orders) == 1
            assert orders[0].coupon_id == coupon.id
            assert orders[0].discount_minor == 7990
            assert product.inventory == 4
    finally:
        test_engine.dispose()
