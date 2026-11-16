import uuid

SEED_NAMESPACE = uuid.UUID("8d8a3d2e-6c4b-5f7a-9e1c-2b4d6f8a0c11")


def seed_id(key: str) -> uuid.UUID:
    """Stable id for a mock-data key so reruns and tests can find the same rows."""
    return uuid.uuid5(SEED_NAMESPACE, key)
