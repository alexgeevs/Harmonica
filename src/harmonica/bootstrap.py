from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from harmonica.models import RatingFactor

DEFAULT_RATING_FACTORS = [
    {
        "key": "lyrics",
        "label": "Lyrics",
        "weight": 1.0,
        "applies_to_lyrics": True,
        "applies_to_instrumental": False,
        "applies_to_variants_only": False,
    },
    {
        "key": "music",
        "label": "Music",
        "weight": 1.0,
        "applies_to_lyrics": True,
        "applies_to_instrumental": True,
        "applies_to_variants_only": False,
    },
    {
        "key": "performance",
        "label": "Performance",
        "weight": 1.0,
        "applies_to_lyrics": True,
        "applies_to_instrumental": True,
        "applies_to_variants_only": True,
    },
    {
        "key": "inspiration",
        "label": "Inspiration",
        "weight": 1.0,
        "applies_to_lyrics": True,
        "applies_to_instrumental": True,
        "applies_to_variants_only": False,
    },
    {
        "key": "focus",
        "label": "Focus",
        "weight": 1.0,
        "applies_to_lyrics": False,
        "applies_to_instrumental": True,
        "applies_to_variants_only": False,
    },
    {
        "key": "overall",
        "label": "Overall",
        "weight": 1.0,
        "applies_to_lyrics": True,
        "applies_to_instrumental": True,
        "applies_to_variants_only": False,
    },
]


def ensure_default_rating_factors(session: Session) -> None:
    existing = set(session.scalars(select(RatingFactor.key)))
    for payload in DEFAULT_RATING_FACTORS:
        if payload["key"] in existing:
            continue
        session.add(RatingFactor(**payload))
    session.commit()
