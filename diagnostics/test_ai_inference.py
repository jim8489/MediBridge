
from types import SimpleNamespace
from unittest.mock import patch

import torch

from django.test import SimpleTestCase

from diagnostics.ai.inference import (
    MODEL_KEY,
    MODEL_VERSION,
    predict_attachment,
)


class FakeChestXRayModel(torch.nn.Module):
    """A lightweight PyTorch model for inference tests."""

    pathologies = [
        "Atelectasis",
        "Effusion",
    ]

    def forward(self, image_tensor):
        return torch.tensor(
            [[0.25, 0.75]],
            dtype=torch.float32,
        )


class InvalidOutputModel(torch.nn.Module):
    """A model that deliberately returns an invalid NaN score."""

    pathologies = [
        "Atelectasis",
        "Effusion",
    ]

    def forward(self, image_tensor):
        return torch.tensor(
            [[float("nan"), 0.5]],
            dtype=torch.float32,
        )


class AIInferenceServiceTests(SimpleTestCase):

    @patch("diagnostics.ai.inference.preprocess_attachment")
    def test_prediction_returns_named_pathology_scores(
        self,
        mock_preprocess,
    ):
        mock_preprocess.return_value = (
            torch.zeros(1, 1, 224, 224),
            {
                "width": 1024,
                "height": 1024,
                "format": "JPEG",
                "channels": 1,
                "model_input_size": 224,
            },
        )

        attachment = SimpleNamespace(
            attachment_type="CLINICAL_IMAGE"
        )

        result = predict_attachment(
            attachment,
            model=FakeChestXRayModel(),
        )

        self.assertEqual(
            result["model_key"],
            MODEL_KEY,
        )

        self.assertEqual(
            result["model_version"],
            MODEL_VERSION,
        )

        self.assertEqual(
            result["pathology_scores"]["Atelectasis"],
            0.25,
        )

        self.assertEqual(
            result["pathology_scores"]["Effusion"],
            0.75,
        )

        self.assertEqual(
            result["output_count"],
            2,
        )

        self.assertIn(
            "not calibrated probabilities",
            result["score_semantics"],
        )

    def test_document_attachment_is_rejected(self):
        attachment = SimpleNamespace(
            attachment_type="REPORT_DOCUMENT"
        )

        with self.assertRaises(ValueError):
            predict_attachment(attachment)

    @patch("diagnostics.ai.inference.preprocess_attachment")
    def test_non_finite_scores_are_rejected(
        self,
        mock_preprocess,
    ):
        mock_preprocess.return_value = (
            torch.zeros(1, 1, 224, 224),
            {
                "width": 224,
                "height": 224,
                "format": "JPEG",
                "channels": 1,
                "model_input_size": 224,
            },
        )

        attachment = SimpleNamespace(
            attachment_type="CLINICAL_IMAGE"
        )

        with self.assertRaises(RuntimeError):
            predict_attachment(
                attachment,
                model=InvalidOutputModel(),
            )
