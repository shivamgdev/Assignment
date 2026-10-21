
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price_minor >= 0", name="ck_products_price_nonnegative"),
        CheckConstraint("inventory >= 0", name="ck_products_inventory_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["CartItem"]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
    )
    order: Mapped["Order | None"] = relationship(back_populates="cart", uselist=False)


class CartItem(Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
        UniqueConstraint("cart_id", "product_id", name="uq_cart_item_product"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("cart_id", name="uq_order_cart"),
        UniqueConstraint("idempotency_key", name="uq_order_idempotency_key"),
        CheckConstraint("gross_total_minor >= 0", name="ck_orders_gross_nonnegative"),
        CheckConstraint("discount_minor >= 0", name="ck_orders_discount_nonnegative"),
        CheckConstraint("net_total_minor >= 0", name="ck_orders_net_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="PLACED", nullable=False)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    coupon_id: Mapped[int | None] = mapped_column(ForeignKey("coupons.id"), nullable=True)
    gross_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    cart: Mapped["Cart"] = relationship(back_populates="order")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    coupon: Mapped["Coupon | None"] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("unit_price_minor >= 0", name="ck_order_items_price_nonnegative"),
        CheckConstraint("line_total_minor >= 0", name="ck_order_items_total_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")


class Coupon(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        UniqueConstraint("milestone_order_count", name="uq_coupon_milestone"),
        CheckConstraint("milestone_order_count > 0", name="ck_coupon_milestone_positive"),
        CheckConstraint("discount_percent > 0 AND discount_percent <= 100", name="ck_coupon_discount_percent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    milestone_order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["Order | None"] = relationship(back_populates="coupon", uselist=False)


class RewardsConfig(Base):
    __tablename__ = "rewards_config"
    __table_args__ = (
        CheckConstraint("orders_per_coupon > 0", name="ck_rewards_orders_per_coupon_positive"),
        CheckConstraint(
            "discount_percent > 0 AND discount_percent <= 100",
            name="ck_rewards_discount_percent",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orders_per_coupon: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )



class CheckoutRequest(Base):
    __tablename__ = "checkout_requests"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_checkout_request_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
