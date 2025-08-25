"""Event-subscribing view singletons for Tk UI.

Each view owns its event subscriptions and delegates rendering to
existing helpers in app where possible to minimize churn.
"""
from __future__ import annotations

from .enemies_view import EnemiesView
from .allies_view import AlliesView
from .resources_view import ResourcesView
from .operations_view import OperationsView

__all__ = [
    "EnemiesView",
    "AlliesView",
    "ResourcesView",
    "OperationsView",
]
