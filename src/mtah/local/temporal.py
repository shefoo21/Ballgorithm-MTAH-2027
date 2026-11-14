"""Opt-in offline adapter. Retain bounded evidence, never a full tracking/feature table."""

from mtah.features import FeatureExtractor
from mtah.inference import EvidenceModel, FeatureContract
from mtah.inference.submission import write_submission
from mtah.inference.temporal import OfflineTemporalDecoder
from mtah.local.diagnostics import OperationalStats
from mtah.local.inputs import iter_inputs


def temporal_pass(config, target, slot_teams, tags):
    stats = OperationalStats(config)
    extractor = FeatureExtractor(config.features, slot_teams, tags)
    model = EvidenceModel(FeatureContract(config.features, slot_teams), config.rules)
    decoder = OfflineTemporalDecoder(fps=config.features.fps, config=config.temporal)

    def evidence():
        for sample in iter_inputs(config):
            stats.observe(sample)
            yield model.score(extractor.transform(sample))

    def predictions():
        for prediction in decoder.decode(evidence()):
            stats.add_prediction(prediction)
            yield prediction

    write_submission(target, predictions(), expected_rows=config.frame_count)
    manifest = model.contract.manifest(model.rules)
    manifest.update(
        {
            "mode": "rules_temporal",
            "implementation": "rules-with-offline-temporal-v1",
            "evidence_implementation": "causal-rules-v1",
            "temporal": decoder.manifest(),
        }
    )
    return stats.finish(), manifest
