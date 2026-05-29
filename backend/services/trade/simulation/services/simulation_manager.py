"""兼容层：统一导出 Trade 主实现的 SimulationAccountManager。"""

from backend.services.trade.services.simulation_manager import SimulationAccountManager

__all__ = ["SimulationAccountManager"]
