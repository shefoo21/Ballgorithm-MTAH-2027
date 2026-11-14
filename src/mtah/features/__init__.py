"""Deterministic team evidence on the tactical video timeline; no possession inference."""

from mtah.features.contracts import (
    FeatureConfig,
    FeatureError,
    FeatureInput,
    HomographyQuality,
    Period,
    TagInterval,
)
from mtah.features.extractor import FeatureExtractor, iter_features
from mtah.features.schema import (
    FrameFeatures,
    HomographyFeatures,
    TagFeatures,
    TeamFeatures,
    feature_schema,
)

__all__ = [
    "FeatureConfig",
    "FeatureError",
    "FeatureExtractor",
    "FeatureInput",
    "FrameFeatures",
    "HomographyFeatures",
    "HomographyQuality",
    "Period",
    "TagFeatures",
    "TagInterval",
    "TeamFeatures",
    "feature_schema",
    "iter_features",
]
