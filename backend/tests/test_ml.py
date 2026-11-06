"""Unit tests for the outcome model and label normalizer (Steps 16-21)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.label_normalizer import UNMAPPED, OutcomeLabelNormalizer
from app.ml.outcome_model import OutcomeModel, OutcomeModelService, fit_classifier


class LabelNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.normalizer = OutcomeLabelNormalizer()

    def test_known_phrasings(self):
        self.assertEqual(self.normalizer.normalize("Appeal allowed"), "allowed")
        self.assertEqual(self.normalizer.normalize("The appeal is dismissed"), "dismissed")
        self.assertEqual(self.normalizer.normalize("convicted"), "convicted")
        self.assertEqual(self.normalizer.normalize("acquitted of all charges"), "acquitted")

    def test_longest_phrase_wins(self):
        self.assertEqual(self.normalizer.normalize("appeal partly allowed"), "partly_allowed")

    def test_unmappable_is_not_forced(self):
        self.assertEqual(self.normalizer.normalize("remanded for reconsideration"), UNMAPPED)
        self.assertEqual(self.normalizer.normalize(None), UNMAPPED)
        self.assertEqual(self.normalizer.normalize(""), UNMAPPED)

    def test_custom_mapping(self):
        normalizer = OutcomeLabelNormalizer(mapping={"affirmed": ["affirmed"]})
        self.assertEqual(normalizer.normalize("judgment affirmed"), "affirmed")


class OutcomeModelTests(unittest.TestCase):
    def test_untrained_service_is_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = OutcomeModelService(Path(tmp) / "missing")
            status = service.status()
            self.assertFalse(status["available"])
            self.assertIn("not currently available", status["reason"])
            prediction = service.predict_from_vectors(np.zeros((1, 4), dtype=np.float32))
            self.assertFalse(prediction["available"])
            self.assertIsNone(prediction["label"])
            self.assertIsNone(prediction["confidence"])

    def test_save_load_roundtrip_and_predict(self):
        rng = np.random.default_rng(0)
        # Two separable clusters so the baseline trains deterministically.
        class_a = rng.normal(loc=0.0, scale=0.05, size=(12, 8))
        class_b = rng.normal(loc=1.0, scale=0.05, size=(12, 8))
        vectors = np.vstack([class_a, class_b])
        labels = ["allowed"] * 12 + ["dismissed"] * 12
        estimator, calibration = fit_classifier(vectors, labels)
        self.assertIn(calibration, {"sigmoid_calibrated", "uncalibrated_logistic"})

        model = OutcomeModel(estimator=estimator, classes=list(estimator.classes_),
                             calibration=calibration, n_train=len(labels))
        with tempfile.TemporaryDirectory() as tmp:
            model.save(Path(tmp))
            loaded = OutcomeModel.load(Path(tmp))
            self.assertIsNotNone(loaded)
            result = loaded.predict(class_b[:1])[0]
            self.assertEqual(result["prediction"], "dismissed")
            self.assertGreater(result["confidence"], 0.5)
            self.assertAlmostEqual(sum(result["probabilities"].values()), 1.0, places=3)

    def test_confidence_reflects_probability(self):
        rng = np.random.default_rng(1)
        vectors = np.vstack([
            rng.normal(0.0, 0.05, (10, 4)),
            rng.normal(1.0, 0.05, (10, 4)),
        ])
        labels = ["allowed"] * 10 + ["dismissed"] * 10
    def test_default_outcome_service_is_available(self):
        from app.ml.outcome_model import outcome_model_service
        outcome_model_service.reload()
        status = outcome_model_service.status()
        self.assertTrue(status["available"])
        self.assertIn("convicted", status["classes"])
        self.assertIn("acquitted", status["classes"])
        self.assertIsNotNone(status["metrics"])
        self.assertGreater(status["metrics"].get("accuracy", 0), 0.5)

    def test_trained_model_predict_from_vectors(self):
        from app.ml.outcome_model import outcome_model_service
        # Generate dummy vector of dimension 384
        vec = np.random.default_rng(42).normal(0.0, 0.1, (1, 384)).astype(np.float32)
        res = outcome_model_service.predict_from_vectors(vec)
        self.assertTrue(res["available"])
        self.assertIn(res["label"], ["convicted", "acquitted"])
        self.assertGreaterEqual(res["confidence"], 0.0)
        self.assertLessEqual(res["confidence"], 1.0)
        self.assertAlmostEqual(sum(res["probabilities"].values()), 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
