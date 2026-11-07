
import os
import tempfile
from functools import lru_cache

import numpy as np
import torch
import torchxrayvision as xrv

from PIL import Image, ImageOps, UnidentifiedImageError


# ---------------------------------------------------------
# MODEL CONFIGURATION
# ---------------------------------------------------------

MODEL_KEY = "torchxrayvision.densenet121-res224-all"
MODEL_VERSION = "1.0"
MODEL_WEIGHTS = "densenet121-res224-all"

MODEL_INPUT_SIZE = 224
MAX_IMAGE_PIXELS = 40_000_000
MAX_FILE_SIZE = 15 * 1024 * 1024

SCORE_SEMANTICS = (
    "Raw TorchXRayVision model output scores. "
    "These are not calibrated probabilities, "
    "clinical diagnoses, or standalone evidence of disease."
)


# ---------------------------------------------------------
# MODEL LOADING
# ---------------------------------------------------------

@lru_cache(maxsize=1)
def load_model():
    """
    Load and cache the pretrained DenseNet121 model.

    The weights are downloaded automatically on first use
    and cached by TorchXRayVision.
    """

    model = xrv.models.DenseNet(
        weights=MODEL_WEIGHTS
    )

    model = model.to(torch.device("cpu"))
    model.eval()

    return model


# ---------------------------------------------------------
# IMAGE PREPROCESSING
# ---------------------------------------------------------

def preprocess_attachment(attachment):
    """
    Convert an uploaded chest X-ray attachment into the
    tensor expected by TorchXRayVision.

    Processing:
        1. Validate attachment type.
        2. Validate file size.
        3. Decode and validate the image.
        4. Correct EXIF orientation.
        5. Convert to grayscale.
        6. Save a temporary normalized-format image.
        7. Load using TorchXRayVision's official loader.
        8. Center crop and resize to 224 x 224.
        9. Return a PyTorch tensor.

    Temporary files are deleted after preprocessing.
    """

    if attachment.attachment_type != "CLINICAL_IMAGE":
        raise ValueError(
            "Only clinical image attachments can be analyzed."
        )

    if attachment.size_bytes > MAX_FILE_SIZE:
        raise ValueError(
            "Image size exceeds the 15 MB limit."
        )

    temporary_path = None

    try:
        # Read the uploaded file from its storage backend.
        with attachment.file.open("rb") as file_handle:

            with Image.open(file_handle) as image:
                image.load()

                image_format = image.format

                if image_format not in ("JPEG", "PNG"):
                    raise ValueError(
                        "Only JPEG and PNG images are supported."
                    )

                width, height = image.size

                if width <= 0 or height <= 0:
                    raise ValueError(
                        "Invalid image dimensions."
                    )

                if width * height > MAX_IMAGE_PIXELS:
                    raise ValueError(
                        "Image dimensions are too large."
                    )

                # Correct image orientation using EXIF metadata.
                image = ImageOps.exif_transpose(image)

                # Chest X-ray models expect a single grayscale channel.
                image = image.convert("L")

                # Save a temporary PNG so that the official
                # TorchXRayVision loader can process it.
                with tempfile.NamedTemporaryFile(
                    suffix=".png",
                    delete=False,
                ) as temporary_file:

                    temporary_path = temporary_file.name

                image.save(
                    temporary_path,
                    format="PNG",
                )

        # Official TorchXRayVision image loading and normalization.
        image_array = xrv.utils.load_image(
            temporary_path
        )

    except (
        OSError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ) as exc:

        raise ValueError(
            "The uploaded image could not be decoded."
        ) from exc

    finally:
        # Always remove the temporary image.
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)

    # Check the normalized image shape.
    if (
        image_array.ndim != 3
        or image_array.shape[0] != 1
    ):
        raise RuntimeError(
            "Unexpected image shape from TorchXRayVision loader."
        )

    # Official model preprocessing.
    image_array = xrv.datasets.XRayCenterCrop()(
        image_array
    )

    image_array = xrv.datasets.XRayResizer(
        MODEL_INPUT_SIZE
    )(image_array)

    # Convert to a batched PyTorch tensor.
    image_tensor = torch.from_numpy(
        np.asarray(image_array, dtype=np.float32)
    ).unsqueeze(0)

    expected_shape = (
        1,
        1,
        MODEL_INPUT_SIZE,
        MODEL_INPUT_SIZE,
    )

    if tuple(image_tensor.shape) != expected_shape:
        raise RuntimeError(
            f"Unexpected model input shape: {image_tensor.shape}"
        )

    if not np.isfinite(image_tensor.numpy()).all():
        raise RuntimeError(
            "Preprocessed image contains invalid numerical values."
        )

    image_metadata = {
        "width": width,
        "height": height,
        "format": image_format,
        "channels": 1,
        "model_input_size": MODEL_INPUT_SIZE,
        "normalization": "TorchXRayVision official loader",
    }

    return image_tensor, image_metadata


# ---------------------------------------------------------
# MODEL INFERENCE
# ---------------------------------------------------------

def predict_attachment(attachment, model=None):
    """
    Perform multi-label chest X-ray inference.

    Returns:
        - Model identifier
        - Model version
        - Pathology scores
        - Score interpretation
        - Image metadata

    This function does not produce clinical diagnoses.
    """

    if attachment.attachment_type != "CLINICAL_IMAGE":
        raise ValueError(
            "AI analysis requires a clinical image."
        )

    # Use the cached pretrained model unless a model
    # is supplied explicitly (useful for automated tests).
    model = model or load_model()

    model.eval()

    # Prepare image.
    image_tensor, image_metadata = preprocess_attachment(
        attachment
    )

    # Run inference without calculating gradients.
    with torch.inference_mode():

        raw_outputs = model(image_tensor)

    # Verify model output.
    if raw_outputs.ndim != 2 or raw_outputs.shape[0] != 1:
        raise RuntimeError(
            "The AI model returned an unexpected output shape."
        )

    outputs = (
        raw_outputs[0]
        .detach()
        .cpu()
        .numpy()
    )

    labels = list(model.pathologies)

    if len(outputs) != len(labels):
        raise RuntimeError(
            "Model output count does not match pathology labels."
        )

    if not np.isfinite(outputs).all():
        raise RuntimeError(
            "The AI model returned non-finite scores."
        )

    # Map every model score to its corresponding pathology.
    pathology_scores = {
        label: round(float(score), 6)
        for label, score in zip(labels, outputs)
    }

    # Return structured inference results.
    return {
        "model_key": MODEL_KEY,
        "model_version": MODEL_VERSION,
        "weights": MODEL_WEIGHTS,

        "pathology_scores": pathology_scores,

        "score_semantics": SCORE_SEMANTICS,

        "image_metadata": image_metadata,

        "output_count": len(pathology_scores),
    }
