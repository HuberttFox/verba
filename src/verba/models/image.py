from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator


class ImageSource(BaseModel):
    """A captured image, supplied either as file path or raw bytes."""

    model_config = ConfigDict(frozen=True)

    path: Path | None = None
    data: bytes | None = None
    mime: str | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> ImageSource:
        if self.path is None and self.data is None:
            raise ValueError("ImageSource requires either 'path' or 'data'")
        return self

    def as_bytes(self) -> bytes:
        """Resolve the image to raw bytes, reading from disk if needed."""
        if self.data is not None:
            return self.data
        if self.path is not None:
            return self.path.read_bytes()
        raise ValueError("ImageSource has neither path nor data")
