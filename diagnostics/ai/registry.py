from diagnostics.models import AIModel

from .inference import (
    MODEL_KEY,
    MODEL_VERSION,
    MODEL_WEIGHTS,
    load_model,
)


def get_registered_model():
    """
    Load the runtime model and register its metadata in PostgreSQL.
    """

    runtime_model = load_model()

    class_labels = list(runtime_model.pathologies)

    defaults = {
        "name": "TorchXRayVision DenseNet121",
        "task_type": AIModel.TaskType.CHEST_XRAY_CLASSIFICATION,
        "framework": "PyTorch / TorchXRayVision",
        "architecture": "DenseNet121",
        "description": (
            "Pretrained multi-label chest X-ray classification "
            "model for research and demonstration purposes."
        ),
        "input_specification": {
            "modality": "Chest X-ray",
            "input_size": 224,
            "channels": 1,
            "image_formats": ["JPEG", "PNG"],
            "normalization": (
                "TorchXRayVision normalization "
                "from 8-bit image intensity."
            ),
            "weights": MODEL_WEIGHTS,
        },
        "class_labels": class_labels,
        "is_active": True,
    }

    database_model, created = AIModel.objects.get_or_create(
        model_key=MODEL_KEY,
        version=MODEL_VERSION,
        defaults=defaults,
    )

    if not database_model.is_active:
        raise RuntimeError(
            "This AI model has been deactivated."
        )

    # Keep registered labels synchronized with the actual
    # loaded model architecture.
    if database_model.class_labels != class_labels:
        database_model.class_labels = class_labels
        database_model.save(update_fields=["class_labels"])

    return database_model, runtime_model