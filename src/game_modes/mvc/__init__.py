"""
MVC模式游戏架构模块

包含：
- Model: 游戏状态管理
- View: 视图渲染
- Controller: 命令处理
"""

from .model import GameModel
from .view import GameView
from .controller import GameController

__all__ = ['GameModel', 'GameView', 'GameController']
