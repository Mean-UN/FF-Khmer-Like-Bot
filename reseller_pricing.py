"""Exact package prices supplied by the owner, stored in USD cents.

Quote each purchase separately. Never apply a larger package's discount to
the combined likes from unrelated purchases.
"""

PACKAGE_PRICES_CENTS = {
    220: 20,
    1000: 50,
    2000: 100,
    3000: 150,
    4000: 200,
    5000: 250,
    6000: 275,
    7000: 325,
    8000: 375,
    9000: 425,
    10000: 450,
    20000: 850,
    30000: 1200,
    50000: 1900,
}


def package_price_cents(likes):
    """Return an exact listed package price; do not infer unlisted prices."""
    if type(likes) is not int or likes not in PACKAGE_PRICES_CENTS:
        raise ValueError("Choose a listed like package")
    return PACKAGE_PRICES_CENTS[likes]


def format_usd(cents):
    if type(cents) is not int:
        raise ValueError("Money must be expressed in whole cents")
    sign = "-" if cents < 0 else ""
    dollars, fraction = divmod(abs(cents), 100)
    return f"{sign}${dollars:,}.{fraction:02d}"
