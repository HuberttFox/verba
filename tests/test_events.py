from __future__ import annotations

from verba.core.events import Event, EventBus, TranslationCompleted
from verba.models.translation import Lang, TranslationResult


def test_subscribe_and_publish() -> None:
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(seen.append, TranslationCompleted)

    event = TranslationCompleted(
        result=TranslationResult(
            text="你好", source=Lang.EN, target=Lang.ZH_HANS, provider="echo"
        )
    )
    bus.publish(event)
    assert seen == [event]


def test_wildcard_subscriber_receives_all() -> None:
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(seen.append)

    event = TranslationCompleted(
        result=TranslationResult(
            text="hi", source=Lang.AUTO, target=Lang.EN, provider="echo"
        )
    )
    bus.publish(event)
    assert seen == [event]


def test_unsubscribe() -> None:
    bus = EventBus()
    seen: list[Event] = []
    bus.subscribe(seen.append, TranslationCompleted)
    bus.unsubscribe(seen.append, TranslationCompleted)
    bus.publish(
        TranslationCompleted(
            result=TranslationResult(
                text="hi", source=Lang.AUTO, target=Lang.EN, provider="echo"
            )
        )
    )
    assert seen == []


def test_handler_error_does_not_break_publish() -> None:
    bus = EventBus()
    good: list[Event] = []
    bus.subscribe(lambda _e: (_ for _ in ()).throw(RuntimeError("boom")))
    bus.subscribe(good.append, TranslationCompleted)

    bus.publish(
        TranslationCompleted(
            result=TranslationResult(
                text="hi", source=Lang.AUTO, target=Lang.EN, provider="echo"
            )
        )
    )
    assert len(good) == 1
