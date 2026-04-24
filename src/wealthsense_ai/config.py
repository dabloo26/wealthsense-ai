from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class DataConfig:
    tickers: list[str] = field(
        default_factory=lambda: [
            "AAPL",
            "MSFT",
            "NVDA",
            "TSLA",
            "SPY",
            "QQQ",
            "VOO",
            "AMZN",
            "GOOGL",
            "META",
        ]
    )
    start_date: str = "2015-01-01"
    end_date: str = "2024-12-31"
    sequence_length: int = 30
    target_column: str = "Close"
    feature_columns: list[str] = field(
        default_factory=lambda: [
            "Close",
            "Volume",
            "SMA_10",
            "SMA_30",
            "EMA_12",
            "RSI_14",
            "Daily_Return",
            "Volatility_10",
        ]
    )


@dataclass(slots=True)
class TrainConfig:
    batch_size: int = 64
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    dropout: float = 0.2
    epochs: int = 30
    patience: int = 6
    hidden_size: int = 64
    num_layers: int = 2
    transformer_heads: int = 4
    transformer_dim: int = 128
    seed: int = 42


@dataclass(slots=True)
class PathsConfig:
    root_dir: Path = Path(__file__).resolve().parents[3]
    artifact_dir: Path = root_dir / "wealthsense-ai" / "artifacts"
    data_cache_dir: Path = artifact_dir / "data_cache"
    model_dir: Path = artifact_dir / "models"
    metrics_file: Path = artifact_dir / "metrics.json"
    forecasts_file: Path = artifact_dir / "forecasts.csv"
    strategy_file: Path = artifact_dir / "strategy_results.csv"

    def ensure(self) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.data_cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir.mkdir(parents=True, exist_ok=True)

