"""Thin Alpaca paper-trading wrapper (alpaca-py).

Keys come from .env / environment: ALPACA_API_KEY, ALPACA_SECRET_KEY.
Always paper mode — this module refuses to construct a live client.

Whole shares only: Alpaca does not allow trailing-stop orders on fractional
positions, so buys are integer-share market orders.
"""

import os
import time

from dotenv import load_dotenv

_client = None


def client():
    global _client
    if _client is None:
        load_dotenv()
        from alpaca.trading.client import TradingClient

        key = os.environ.get("ALPACA_API_KEY")
        secret = os.environ.get("ALPACA_SECRET_KEY")
        if not key or not secret:
            raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY not set (see .env.example)")
        _client = TradingClient(key, secret, paper=True)
    return _client


def account():
    return client().get_account()


def positions():
    return client().get_all_positions()


def buy_market(ticker: str, qty: int):
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    return client().submit_order(
        MarketOrderRequest(
            symbol=ticker, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.DAY
        )
    )


def sell_market(ticker: str, qty: int):
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    return client().submit_order(
        MarketOrderRequest(
            symbol=ticker, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.DAY
        )
    )


def trailing_stop(ticker: str, qty: int, trail_pct: float):
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import TrailingStopOrderRequest

    return client().submit_order(
        TrailingStopOrderRequest(
            symbol=ticker,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC,
            trail_percent=trail_pct,
        )
    )


def cancel_open_orders(ticker: str) -> None:
    """Cancel open orders for a symbol (e.g. old trailing stop before a sell)."""
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    orders = client().get_orders(
        GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[ticker])
    )
    for o in orders:
        client().cancel_order_by_id(o.id)


def market_open_today() -> bool:
    """True if today is a trading day — holiday/weekend guard. Uses the
    calendar (not the clock) so it stays True after the 4pm close, which the
    end-of-day and weekly routines rely on."""
    from alpaca.trading.requests import GetCalendarRequest

    today = client().get_clock().timestamp.date()
    days = client().get_calendar(GetCalendarRequest(start=today, end=today))
    return bool(days) and days[0].date == today


def open_orders():
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    return client().get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))


def todays_filled_orders():
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    from datetime import datetime, time as dtime, timezone

    midnight = datetime.combine(datetime.now(timezone.utc).date(), dtime.min, timezone.utc)
    orders = client().get_orders(
        GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=midnight, limit=200)
    )
    return [o for o in orders if o.filled_at is not None]


def portfolio_history(period: str = "1W"):
    """Equity curve over the period (dict with equity list + timestamps)."""
    from alpaca.trading.requests import GetPortfolioHistoryRequest

    return client().get_portfolio_history(
        GetPortfolioHistoryRequest(period=period, timeframe="1D")
    )


def wait_for_fill(order_id, timeout_s: int = 120):
    """Poll until the order fills (or times out). Returns the final order."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        o = client().get_order_by_id(order_id)
        if str(o.status) in ("OrderStatus.FILLED", "filled"):
            return o
        if str(o.status) in ("OrderStatus.CANCELED", "canceled", "OrderStatus.REJECTED", "rejected"):
            raise RuntimeError(f"order {order_id} ended {o.status}")
        time.sleep(2)
    raise TimeoutError(f"order {order_id} not filled within {timeout_s}s")
