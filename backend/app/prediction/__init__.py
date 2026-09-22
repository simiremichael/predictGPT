"""Prediction engine for football match outcome probabilities.

This package implements the statistical prediction layer that sits between
normalized football data (from any provider) and the API/database layers.

Architecture:
    Normalized data → Feature Engineering → Model → Score Matrix → Markets → Output

The prediction engine is completely independent of any specific data provider.
It only consumes Normalized* models from football_data.models.
"""
from __future__ import annotations

__version__ = "1.0.0"
__model_version__ = "poisson-v1.0.0"
