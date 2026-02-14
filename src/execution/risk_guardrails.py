from dataclasses import dataclass


@dataclass
class RiskGuardrails:
    max_trades_per_day: int = 3
    max_daily_loss_abs: float = 1.0
    max_consecutive_losses: int = 3


class RiskState:
    def __init__(self):
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.locked = False

    def allow_new_trade(self, cfg: RiskGuardrails) -> bool:
        if self.locked:
            return False
        if self.trades_today >= cfg.max_trades_per_day:
            return False
        if self.daily_pnl <= -abs(cfg.max_daily_loss_abs):
            return False
        if self.consecutive_losses >= cfg.max_consecutive_losses:
            return False
        return True

    def on_trade_close(self, pnl_abs: float, cfg: RiskGuardrails):
        self.trades_today += 1
        self.daily_pnl += float(pnl_abs)
        if pnl_abs <= 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        if (
            self.trades_today >= cfg.max_trades_per_day
            or self.daily_pnl <= -abs(cfg.max_daily_loss_abs)
            or self.consecutive_losses >= cfg.max_consecutive_losses
        ):
            self.locked = True

    def reset_day(self):
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.locked = False
