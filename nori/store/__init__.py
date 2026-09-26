"""Nori's growth strategies for the virtual paper store.

Uses Taro's engine in ``taro.store`` (read-only).
"""

from .strategy import GrowthStrategy, NaiveBaseline, Strategy

__all__ = ["GrowthStrategy", "NaiveBaseline", "Strategy"]
