"""verba — a UI-agnostic plugin framework for building Bob/Pot-style tools.

Core is headless: no GUI dependency. Desktop UIs (PySide6, Tkinter, ...)
plug in later through the OutputHandler / InputSource abstractions.
"""

from verba import core, inputs, models, outputs, providers
from verba.core.events import EventBus
from verba.core.pipeline import Pipeline, PipelineAction
from verba.core.registry import ServiceRegistry

__version__ = "0.1.0"

__all__ = [
    "EventBus",
    "Pipeline",
    "PipelineAction",
    "ServiceRegistry",
    "core",
    "inputs",
    "models",
    "outputs",
    "providers",
    "__version__",
]
