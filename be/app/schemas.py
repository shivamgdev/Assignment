
from pydantic import BaseModel, ConfigDict, Field




class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit_price_minor: int
    inventory: int


class CartCreateResponse(BaseModel):
    id: int
    status: str


class CartItemInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=1000)


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0, le=1000)


class CartItemResponse(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    unit_price_minor: int
    line_total_minor: int


class CartResponse(BaseModel):
    id: int
    status: str
    items: list[CartItemResponse]
    total_minor: int


class ErrorResponse(BaseModel):
    detail: str


class OrderItemResponse(BaseModel):
    product_id: int
    product_name: str
    unit_price_minor: int
    quantity: int
    line_total_minor: int


class OrderResponse(BaseModel):
    id: int
    cart_id: int
    status: str
    gross_total_minor: int
    discount_minor: int
    net_total_minor: int
    items: list[OrderItemResponse]



class RewardsConfigInput(BaseModel):
    orders_per_coupon: int = Field(gt=0, le=1000000)
    discount_percent: int = Field(gt=0, le=100)


class RewardsConfigResponse(BaseModel):
    id: int
    orders_per_coupon: int
    discount_percent: int



class CouponResponse(BaseModel):
    id: int
    code: str
    milestone_order_count: int
    discount_percent: int
    redeemed_at: str | None


class CouponGenerationResponse(BaseModel):
    generated: bool
    message: str
    coupon: CouponResponse | None


class ProductSummaryItem(BaseModel):
    product_id: int
    product_name: str
    quantity_sold: int


class AdminSummaryReport(BaseModel):
    total_successful_orders: int
    gross_revenue_minor: int
    total_discounts_minor: int
    net_revenue_minor: int
    coupons_generated: int
    coupons_available: int
    coupons_redeemed: int
    products: list[ProductSummaryItem]
