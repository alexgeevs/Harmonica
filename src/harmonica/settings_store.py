from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from harmonica.config import Settings
from harmonica.models import AppSetting

SettingType = Literal["number", "boolean"]
ControlType = Literal["slider", "stepper", "switch"]


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    label: str
    description: str
    value_type: SettingType
    control: ControlType
    default: float | int | bool
    minimum: float | int | None = None
    maximum: float | int | None = None
    step: float | int | None = None
    unit: str | None = None


SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition(
        key="default_playlist_length",
        label="Default playlist length",
        description="How many tracks Harmonica suggests when the queue screen opens.",
        value_type="number",
        control="stepper",
        default=100,
        minimum=1,
        maximum=1000,
        step=1,
        unit="tracks",
    ),
    SettingDefinition(
        key="beta",
        label="Group size strength",
        description=(
            "Controls how much bigger groups benefit from having more songs. Higher values "
            "make large groups more prominent, but the logarithmic curve still limits dominance."
        ),
        value_type="number",
        control="slider",
        default=1.25,
        minimum=0.0,
        maximum=3.0,
        step=0.05,
    ),
    SettingDefinition(
        key="group_cooldown_floor",
        label="Group repeat floor",
        description=(
            "The lowest chance a just-played group keeps. Lower values push musicals, artists, "
            "or themes farther apart; higher values allow repeats sooner."
        ),
        value_type="number",
        control="slider",
        default=0.05,
        minimum=0.0,
        maximum=0.5,
        step=0.01,
    ),
    SettingDefinition(
        key="sub_group_cooldown_floor",
        label="Variant repeat floor",
        description=(
            "The lowest chance a just-played cover/reprise/version family keeps. Lower values "
            "make variants of the same song much less likely to appear close together."
        ),
        value_type="number",
        control="slider",
        default=0.01,
        minimum=0.0,
        maximum=0.25,
        step=0.01,
    ),
    SettingDefinition(
        key="song_rating_min_multiplier",
        label="Lowest song rating multiplier",
        description=(
            "The multiplier used for a 0-star effective song rating. Lower values punish "
            "poorly-rated songs more strongly."
        ),
        value_type="number",
        control="slider",
        default=0.5,
        minimum=0.1,
        maximum=1.0,
        step=0.05,
    ),
    SettingDefinition(
        key="song_rating_max_multiplier",
        label="Highest song rating multiplier",
        description=(
            "The multiplier used for a 5-star effective song rating. Higher values make "
            "favourites more prominent, with more risk of over-focusing on them."
        ),
        value_type="number",
        control="slider",
        default=2.0,
        minimum=1.0,
        maximum=3.0,
        step=0.05,
    ),
    SettingDefinition(
        key="enable_group_rating_multiplier",
        label="Use group rating multiplier",
        description=(
            "Experimental. When enabled, stored group rating multipliers affect queue generation. "
            "Leave off while group-rating aggregation is still being tuned."
        ),
        value_type="boolean",
        control="switch",
        default=False,
    ),
)

SETTING_MAP = {definition.key: definition for definition in SETTING_DEFINITIONS}


def get_setting_values(session: Session, base_settings: Settings) -> dict[str, float | int | bool]:
    stored = {row.key: json.loads(row.value_json) for row in session.scalars(select(AppSetting))}
    values: dict[str, float | int | bool] = {}
    for definition in SETTING_DEFINITIONS:
        base_value = getattr(base_settings, definition.key)
        values[definition.key] = sanitize_value(definition, stored.get(definition.key, base_value))
    return values


def get_effective_settings(session: Session, base_settings: Settings) -> Settings:
    return base_settings.model_copy(update=get_setting_values(session, base_settings))


def update_setting_values(
    session: Session,
    updates: dict[str, Any],
    base_settings: Settings,
) -> dict[str, float | int | bool]:
    current = get_setting_values(session, base_settings)
    for key, raw_value in updates.items():
        definition = SETTING_MAP.get(key)
        if definition is None:
            continue
        value = sanitize_value(definition, raw_value)
        current[key] = value
        row = session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value_json=json.dumps(value))
            session.add(row)
        else:
            row.value_json = json.dumps(value)
    session.commit()
    return current


def settings_payload(session: Session, base_settings: Settings) -> dict[str, Any]:
    values = get_setting_values(session, base_settings)
    return {
        **values,
        "home": str(base_settings.home),
        "host": base_settings.host,
        "port": base_settings.port,
        "group_rating_min_multiplier": base_settings.group_rating_min_multiplier,
        "group_rating_max_multiplier": base_settings.group_rating_max_multiplier,
        "controls": [
            {
                "key": definition.key,
                "label": definition.label,
                "description": definition.description,
                "value_type": definition.value_type,
                "control": definition.control,
                "default": definition.default,
                "minimum": definition.minimum,
                "maximum": definition.maximum,
                "step": definition.step,
                "unit": definition.unit,
                "value": values[definition.key],
            }
            for definition in SETTING_DEFINITIONS
        ],
    }


def sanitize_value(definition: SettingDefinition, raw_value: Any) -> float | int | bool:
    if definition.value_type == "boolean":
        return bool(raw_value)
    value = float(raw_value)
    if definition.minimum is not None:
        value = max(float(definition.minimum), value)
    if definition.maximum is not None:
        value = min(float(definition.maximum), value)
    if isinstance(definition.default, int):
        return int(round(value))
    return value

