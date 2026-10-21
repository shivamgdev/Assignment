from sqlalchemy import select, text, update , func
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timezone

import secrets
import string

from app.models import (
    Cart,
    CartItem,
    CheckoutRequest,
    Order,
    OrderItem,
    Product,
    RewardsConfig,
    Coupon,
)

class ServiceError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def get_rewards_config(db: Session) -> RewardsConfig:
    config = db.scalar(
        select(RewardsConfig).order_by(RewardsConfig.id).limit(1)
    )

    if config is None:
        raise ServiceError(404, "Rewards configuration has not been set")

    return config


def set_rewards_config(
    db: Session,
    orders_per_coupon: int,
    discount_percent: int,
) -> RewardsConfig:
    if orders_per_coupon <= 0:
        raise ServiceError(422, "Orders per coupon must be positive")

    if not 1 <= discount_percent <= 100:
        raise ServiceError(422, "Discount percent must be between 1 and 100")

    try:
        config = db.scalar(
            select(RewardsConfig).order_by(RewardsConfig.id).limit(1)
        )

        if config is None:
            config = RewardsConfig(
                orders_per_coupon=orders_per_coupon,
                discount_percent=discount_percent,
            )
            db.add(config)
        else:
            config.orders_per_coupon = orders_per_coupon
            config.discount_percent = discount_percent

        db.commit()
        db.refresh(config)
        return config
    except Exception:
        db.rollback()
        raise



def generate_reward_coupon(db: Session) -> dict:
    try:
        db.execute(text("BEGIN IMMEDIATE"))

        config = db.scalar(
            select(RewardsConfig).order_by(RewardsConfig.id).limit(1)
        )

        if config is None:
            raise ServiceError(
                409,
                "Rewards configuration has not been set",
            )

        successful_orders = db.scalar(
            select(func.count(Order.id)).where(Order.status == "PLACED")
        ) or 0

        if successful_orders < config.orders_per_coupon:
            raise ServiceError(
                409,
                "No rewards milestone has been reached yet",
            )

        generated_milestones = set(
            db.scalars(
                select(Coupon.milestone_order_count)
            ).all()
        )

        eligible_milestone = next(
            (
                milestone
                for milestone in range(
                    config.orders_per_coupon,
                    successful_orders + 1,
                    config.orders_per_coupon,
                )
                if milestone not in generated_milestones
            ),
            None,
        )

        if eligible_milestone is None:
            db.commit()
            return {
                "generated": False,
                "message": "All reached rewards milestones already have coupons",
                "coupon": None,
            }

        alphabet = string.ascii_uppercase + string.digits
        code = "REWARD-" + "".join(
            secrets.choice(alphabet) for _ in range(10)
        )

        while db.scalar(
            select(Coupon.id).where(Coupon.code == code)
        ) is not None:
            code = "REWARD-" + "".join(
                secrets.choice(alphabet) for _ in range(10)
            )

        coupon = Coupon(
            code=code,
            milestone_order_count=eligible_milestone,
            discount_percent=config.discount_percent,
        )

        db.add(coupon)
        db.flush()
        db.commit()
        db.refresh(coupon)

        return {
            "generated": True,
            "message": "Reward coupon generated successfully",
            "coupon": coupon,
        }

    except Exception:
        db.rollback()
        raise


def get_cart(db: Session, cart_id: int) -> Cart:
    cart = db.scalar(
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.product))
        .where(Cart.id == cart_id)
    )

    if cart is None:
        raise ServiceError(404, "Cart not found")

    return cart


def ensure_cart_open(cart: Cart):
    if cart.status != "OPEN":
        raise ServiceError(409, "Cart has already been checked out")


def create_cart(db: Session) -> Cart:
    cart = Cart(status="OPEN")
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def add_cart_item(db: Session, cart_id: int, product_id: int, quantity: int) -> Cart:
    cart = get_cart(db, cart_id)
    ensure_cart_open(cart)

    product = db.get(Product, product_id)
    if product is None:
        raise ServiceError(404, "Product not found")

    existing_item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        )
    )

    new_quantity = quantity + (existing_item.quantity if existing_item else 0)

    if new_quantity > 1000:
        raise ServiceError(422, "Combined quantity cannot exceed 1000")

    if new_quantity > product.inventory:
        raise ServiceError(409, "Requested quantity exceeds current inventory")

    if existing_item:
        existing_item.quantity = new_quantity
    else:
        db.add(CartItem(cart_id=cart_id, product_id=product_id, quantity=quantity))

    db.commit()
    db.expire_all()
    return get_cart(db, cart_id)


def update_cart_item(db: Session, cart_id: int, product_id: int, quantity: int) -> Cart:
    cart = get_cart(db, cart_id)
    ensure_cart_open(cart)

    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        )
    )

    if item is None:
        raise ServiceError(404, "Product is not in this cart")

    product = db.get(Product, product_id)
    if product is None:
        raise ServiceError(404, "Product not found")

    if quantity > product.inventory:
        raise ServiceError(409, "Requested quantity exceeds current inventory")

    item.quantity = quantity
    db.commit()
    return get_cart(db, cart_id)


def remove_cart_item(db: Session, cart_id: int, product_id: int) -> Cart:
    cart = get_cart(db, cart_id)
    ensure_cart_open(cart)

    item = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        )
    )

    if item is None:
        raise ServiceError(404, "Product is not in this cart")

    db.delete(item)
    db.commit()
    db.expire_all()
    return get_cart(db, cart_id)


def serialize_cart(cart: Cart) -> dict:
    items = []
    total_minor = 0

    for item in cart.items:
        unit_price = item.product.unit_price_minor
        line_total = unit_price * item.quantity
        total_minor += line_total
        items.append(
            {
                "product_id": item.product_id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price_minor": unit_price,
                "line_total_minor": line_total,
            }
        )

    return {
        "id": cart.id,
        "status": cart.status,
        "items": items,
        "total_minor": total_minor,
    }

def get_order(db: Session, order_id: int) -> Order:
    order = db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )

    if order is None:
        raise ServiceError(404, "Order not found")

    return order


def serialize_order(order: Order) -> dict:
    return {
        "id": order.id,
        "cart_id": order.cart_id,
        "status": order.status,
        "gross_total_minor": order.gross_total_minor,
        "discount_minor": order.discount_minor,
        "net_total_minor": order.net_total_minor,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "unit_price_minor": item.unit_price_minor,
                "quantity": item.quantity,
                "line_total_minor": item.line_total_minor,
            }
            for item in order.items
        ],
    }



def checkout_cart(
    db: Session,
    cart_id: int,
    idempotency_key: str,
    coupon_code: str | None = None,
) -> Order:
    if not idempotency_key or len(idempotency_key) > 200:
        raise ServiceError(
            422,
            "Idempotency-Key must contain 1 to 200 characters",
        )

    if coupon_code is not None:
        coupon_code = coupon_code.strip().upper()

        if not coupon_code or len(coupon_code) > 64:
            raise ServiceError(422, "Invalid coupon code")

    try:
        db.execute(text("BEGIN IMMEDIATE"))

        previous_request = db.scalar(
            select(CheckoutRequest).where(
                CheckoutRequest.idempotency_key == idempotency_key
            )
        )

        if previous_request is not None:
            if (
                previous_request.cart_id != cart_id
                or previous_request.coupon_code != coupon_code
            ):
                raise ServiceError(
                    409,
                    "Idempotency-Key was already used for a different checkout request",
                )

            order = get_order(db, previous_request.order_id)
            db.commit()
            return order

        cart = db.scalar(
            select(Cart)
            .options(
                selectinload(Cart.items).selectinload(CartItem.product)
            )
            .where(Cart.id == cart_id)
        )

        if cart is None:
            raise ServiceError(404, "Cart not found")

        ensure_cart_open(cart)

        if not cart.items:
            raise ServiceError(409, "Cannot checkout an empty cart")

        coupon = None

        if coupon_code is not None:
            coupon = db.scalar(
                select(Coupon).where(Coupon.code == coupon_code)
            )

            if coupon is None:
                raise ServiceError(422, "Invalid coupon code")

            if coupon.redeemed_at is not None:
                raise ServiceError(409, "Coupon has already been redeemed")

        order_lines = []
        gross_total_minor = 0

        for item in cart.items:
            product = db.get(Product, item.product_id)

            if product is None:
                raise ServiceError(404, "Product not found")

            result = db.execute(
                update(Product)
                .where(
                    Product.id == product.id,
                    Product.inventory >= item.quantity,
                )
                .values(
                    inventory=Product.inventory - item.quantity
                )
            )

            if result.rowcount != 1:
                raise ServiceError(
                    409,
                    f"Insufficient inventory for product {product.id}",
                )

            line_total_minor = product.unit_price_minor * item.quantity
            gross_total_minor += line_total_minor

            order_lines.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "unit_price_minor": product.unit_price_minor,
                    "quantity": item.quantity,
                    "line_total_minor": line_total_minor,
                }
            )

        discount_minor = 0
        coupon_id = None

        if coupon is not None:
            discount_minor = (
                gross_total_minor * coupon.discount_percent + 50
            ) // 100

            discount_minor = min(discount_minor, gross_total_minor)

            redemption_time = datetime.now(timezone.utc)

            redemption_result = db.execute(
                update(Coupon)
                .where(
                    Coupon.id == coupon.id,
                    Coupon.redeemed_at.is_(None),
                )
                .values(redeemed_at=redemption_time)
            )

            if redemption_result.rowcount != 1:
                raise ServiceError(
                    409,
                    "Coupon has already been redeemed",
                )

            coupon_id = coupon.id

        net_total_minor = gross_total_minor - discount_minor

        order = Order(
            cart_id=cart.id,
            idempotency_key=idempotency_key,
            status="PLACED",
            coupon_id=coupon_id,
            gross_total_minor=gross_total_minor,
            discount_minor=discount_minor,
            net_total_minor=net_total_minor,
        )

        db.add(order)
        db.flush()

        for line in order_lines:
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=line["product_id"],
                    product_name=line["product_name"],
                    unit_price_minor=line["unit_price_minor"],
                    quantity=line["quantity"],
                    line_total_minor=line["line_total_minor"],
                )
            )

        cart.status = "CHECKED_OUT"
        cart.checked_out_at = (
            cart.checked_out_at or datetime.now(timezone.utc)
        )

        db.add(
            CheckoutRequest(
                idempotency_key=idempotency_key,
                cart_id=cart.id,
                coupon_code=coupon_code,
                order_id=order.id,
            )
        )

        db.flush()
        db.commit()

        return get_order(db, order.id)

    except Exception:
        db.rollback()
        raise



def get_admin_summary_report(db: Session) -> dict:
    total_successful_orders = db.scalar(
        select(func.count(Order.id)).where(Order.status == "PLACED")
    ) or 0

    gross_revenue_minor = db.scalar(
        select(func.coalesce(func.sum(Order.gross_total_minor), 0)).where(
            Order.status == "PLACED"
        )
    ) or 0

    total_discounts_minor = db.scalar(
        select(func.coalesce(func.sum(Order.discount_minor), 0)).where(
            Order.status == "PLACED"
        )
    ) or 0

    net_revenue_minor = db.scalar(
        select(func.coalesce(func.sum(Order.net_total_minor), 0)).where(
            Order.status == "PLACED"
        )
    ) or 0

    product_rows = db.execute(
        select(
            OrderItem.product_id,
            OrderItem.product_name,
            func.sum(OrderItem.quantity).label("quantity_sold"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status == "PLACED")
        .group_by(OrderItem.product_id, OrderItem.product_name)
        .order_by(OrderItem.product_name)
    ).all()

    coupons_generated = db.scalar(
        select(func.count(Coupon.id))
    ) or 0

    coupons_redeemed = db.scalar(
        select(func.count(Coupon.id)).where(
            Coupon.redeemed_at.is_not(None)
        )
    ) or 0

    return {
        "total_successful_orders": total_successful_orders,
        "gross_revenue_minor": gross_revenue_minor,
        "total_discounts_minor": total_discounts_minor,
        "net_revenue_minor": net_revenue_minor,
        "coupons_generated": coupons_generated,
        "coupons_available": coupons_generated - coupons_redeemed,
        "coupons_redeemed": coupons_redeemed,
        "products": [
            {
                "product_id": row.product_id,
                "product_name": row.product_name,
                "quantity_sold": row.quantity_sold,
            }
            for row in product_rows
        ],
    }
