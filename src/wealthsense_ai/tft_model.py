from __future__ import annotations

import torch
from torch import nn


class TFTRegressor(nn.Module):
    """
    Lightweight TFT-compatible regressor interface.
    Uses a small fallback network when pytorch-forecasting is unavailable.
    """

    def __init__(self, input_size: int, hidden_size: int, dropout: float) -> None:
        super().__init__()
        self.backbone = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=2,
            dropout=dropout,
            batch_first=True,
        )
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.backbone(x)
        return self.head(out[:, -1, :]).squeeze(-1)
