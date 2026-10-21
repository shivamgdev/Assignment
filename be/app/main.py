
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import Product
from app.schemas import (
    CartCreateResponse,
    CartItemInput,
    CartItemUpdate,
    CartResponse,
    OrderResponse,
    ProductResponse,
    RewardsConfigInput,
    RewardsConfigResponse,
    CouponGenerationResponse,
    AdminSummaryReport,
)
from app.services import (
    ServiceError,
    add_cart_item,
    checkout_cart,
    create_cart,
    get_cart,
    remove_cart_item,
    serialize_cart,
    serialize_order,
    update_cart_item,
    get_order,
    get_rewards_config,
    set_rewards_config,
    generate_reward_coupon,
    get_admin_summary_report,
)


def initialize_database():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        existing_product = db.scalar(select(Product.id).limit(1))

        if existing_product is None:
            db.add_all(
                [
                    Product(name="Wireless Mouse", unit_price_minor=79900, inventory=25),
                    Product(name="Mechanical Keyboard", unit_price_minor=249900, inventory=12),
                    Product(name="USB-C Cable", unit_price_minor=49900, inventory=50),
                    Product(name="Laptop Stand", unit_price_minor=159900, inventory=8),
                    Product(name="USB-C Hub", unit_price_minor=199900, inventory=3),
                ]
            )
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Reliable Checkout and Rewards Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ServiceError)
async def handle_service_error(request, exc: ServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/products", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.id)).all()


@app.post("/carts", response_model=CartCreateResponse, status_code=201)
def create_new_cart(db: Session = Depends(get_db)):
    cart = create_cart(db)
    return {"id": cart.id, "status": cart.status}


@app.get("/carts/{cart_id}", response_model=CartResponse)
def retrieve_cart(cart_id: int, db: Session = Depends(get_db)):
    cart = get_cart(db, cart_id)
    return serialize_cart(cart)


@app.post("/carts/{cart_id}/items", response_model=CartResponse)
def add_item(
    cart_id: int,
    payload: CartItemInput,
    db: Session = Depends(get_db),
):
    cart = add_cart_item(
        db,
        cart_id,
        payload.product_id,
        payload.quantity,
    )
    return serialize_cart(cart)


@app.put("/carts/{cart_id}/items/{product_id}", response_model=CartResponse)
def update_item(
    cart_id: int,
    product_id: int,
    payload: CartItemUpdate,
    db: Session = Depends(get_db),
):
    cart = update_cart_item(
        db,
        cart_id,
        product_id,
        payload.quantity,
    )
    return serialize_cart(cart)


@app.delete("/carts/{cart_id}/items/{product_id}", response_model=CartResponse)
def remove_item(
    cart_id: int,
    product_id: int,
    db: Session = Depends(get_db),
):
    cart = remove_cart_item(db, cart_id, product_id)
    return serialize_cart(cart)


@app.post(
    "/carts/{cart_id}/checkout",
    response_model=OrderResponse,
    status_code=201,
)
def checkout(
    cart_id: int,
    coupon_code: str | None = None,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=200,
    ),
    db: Session = Depends(get_db),
):
    order = checkout_cart(
        db,
        cart_id,
        idempotency_key,
        coupon_code,
    )
    return serialize_order(order)


@app.get("/orders/{order_id}", response_model=OrderResponse)
def retrieve_order(order_id: int, db: Session = Depends(get_db)):
    order = get_order(db, order_id)
    return serialize_order(order)



@app.get("/admin/rewards/config", response_model=RewardsConfigResponse)
def retrieve_rewards_config(db: Session = Depends(get_db)):
    return get_rewards_config(db)


@app.put("/admin/rewards/config", response_model=RewardsConfigResponse)
def update_rewards_config(
    payload: RewardsConfigInput,
    db: Session = Depends(get_db),
):
    return set_rewards_config(
        db,
        payload.orders_per_coupon,
        payload.discount_percent,
    )


@app.post(
    "/admin/rewards/coupons/generate",
    response_model=CouponGenerationResponse,
)
def generate_reward_coupon_endpoint(db: Session = Depends(get_db)):
    return generate_reward_coupon(db)


@app.get(
    "/admin/reports/summary",
    response_model=AdminSummaryReport,
)
def retrieve_admin_summary_report(db: Session = Depends(get_db)):
    return get_admin_summary_report(db)
