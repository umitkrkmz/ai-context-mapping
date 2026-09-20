"""Business constants. All amounts are integer cents; rates are in basis points (1/100 of a percent)."""

FREE_SHIPPING_MIN_CENTS = 5000
FLAT_RATE_CENTS = {"domestic": 599, "regional": 899, "international": 1999}
PER_KG_SURCHARGE_CENTS = 150
FREE_WEIGHT_ALLOWANCE_GRAMS = 1000
TAX_RATES_BPS = {"CA": 725, "NY": 888, "TX": 625, "OR": 0}
BULK_DISCOUNT_MIN_ITEMS = 10
BULK_DISCOUNT_BPS = 500
COUPONS_BPS = {"WELCOME10": 1000, "SPRING5": 500}
DATA_DIR_ENV = "SHIPDESK_DATA_DIR"
