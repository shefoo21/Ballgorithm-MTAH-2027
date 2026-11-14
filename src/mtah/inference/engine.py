"""Composition API: immutable features -> evidence -> causal predictions."""

from collections.abc import Iterable, Iterator

from mtah.features import FrameFeatures
from mtah.inference.contracts import FeatureContract, Prediction, RuleConfig
from mtah.inference.decoder import RuleDecoder
from mtah.inference.evidence import EvidenceModel


class PossessionEngine:
    def __init__(self, contract: FeatureContract, rules: RuleConfig | None = None):
        self._model = EvidenceModel(contract, rules)
        self._decoder = RuleDecoder(fps=contract.config.fps, rules=self._model.rules)

    def step(self, features: FrameFeatures) -> Prediction:
        return self._decoder.step(self._model.score(features))

    def manifest(self) -> dict:
        return self._model.contract.manifest(self._model.rules)


def iter_predictions(
    features: Iterable[FrameFeatures], *, contract: FeatureContract, rules: RuleConfig | None = None
) -> Iterator[Prediction]:
    engine = PossessionEngine(contract, rules)
    for frame in features:
        yield engine.step(frame)
