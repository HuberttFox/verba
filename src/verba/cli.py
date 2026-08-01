"""CLI demo: prove the framework works end-to-end without a GUI.

    verba translate "Hello world" --to zh-Hans
    verba ocr-demo ./screenshot.png
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Callable, cast

from verba.config.loader import load_config
from verba.core.pipeline import Pipeline, PipelineAction
from verba.core.registry import ServiceRegistry
from verba.inputs.base import InputSourceRegistry
from verba.models.translation import Lang
from verba.outputs.base import OutputHub
from verba.outputs.notification import ConsoleOutputHandler
from verba.providers.base import BaseOCR, BaseTranslator
from verba.providers.demo import EchoOCR, EchoTranslator
from verba.utils.cache import TTLCache
from verba.utils.log import setup_logging


def build_pipeline() -> Pipeline:
    translators: ServiceRegistry[BaseTranslator] = ServiceRegistry()
    ocr: ServiceRegistry[BaseOCR] = ServiceRegistry()
    translators.register("echo", EchoTranslator())
    ocr.register("echo-ocr", EchoOCR())

    outputs = OutputHub()
    outputs.register(ConsoleOutputHandler())

    config = load_config()
    return Pipeline(
        translators=translators,
        ocr=ocr,
        inputs=InputSourceRegistry(),
        outputs=outputs,
        cache=TTLCache(
            ttl_seconds=config.cache.ttl_seconds,
            max_entries=config.cache.max_entries,
        ),
    )


def cmd_translate(args: argparse.Namespace, pipeline: Pipeline) -> int:
    pipeline.translate_text(
        text=args.text,
        target_lang=Lang(args.to),
        source=Lang(args.from_lang),
        provider=args.provider,
    )
    return 0


def cmd_ocr(args: argparse.Namespace, pipeline: Pipeline) -> int:
    from verba.models.image import ImageSource

    pipeline.run(
        PipelineAction(
            name="ocr-demo",
            needs_ocr=True,
            ocr_provider=args.provider,
            translator_provider=None,
        ),
        image=ImageSource(path=args.image),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    setup_logging(logging.INFO)
    parser = argparse.ArgumentParser(prog="verba", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("translate", help="translate text")
    p.add_argument("text")
    p.add_argument("--from", dest="from_lang", default=Lang.AUTO.value)
    p.add_argument("--to", default=Lang.ZH_HANS.value)
    p.add_argument("--provider", default="echo")
    p.set_defaults(fn=cmd_translate)

    p = sub.add_parser("ocr-demo", help="OCR an image, then translate the text")
    p.add_argument("image")
    p.add_argument("--provider", default="echo-ocr")
    p.set_defaults(fn=cmd_ocr)

    args = parser.parse_args(argv)
    try:
        fn = cast("Callable[[argparse.Namespace, Pipeline], int]", args.fn)
        return fn(args, build_pipeline())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
