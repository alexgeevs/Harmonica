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
            "When enabled, song ratings are aggregated into group multipliers so strongly rated "
            "sources, artists, and themes get more long-run weight."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="history_influence_enabled",
        label="Use playback history",
        description=(
            "When enabled, completed listens and meaningful partial listens affect future repeat "
            "cooldowns. Very early skips become negative utility signals instead."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="skip_penalty_strength",
        label="Skip penalty strength",
        description=(
            "How strongly very early skips reduce future utility. A 10% skip is treated as a "
            "bad signal, while a partial listen under 50% is a milder bad signal."
        ),
        value_type="number",
        control="slider",
        default=0.25,
        minimum=0.0,
        maximum=0.75,
        step=0.05,
    ),
    SettingDefinition(
        key="cold_start_enabled",
        label="Startup coverage mode",
        description=(
            "Boost unrated songs while the library is still being learned, so songs are not "
            "abandoned before they have had a fair chance."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="cold_start_unrated_boost",
        label="Unrated song boost",
        description=(
            "How much extra weight unrated songs receive during startup coverage mode."
        ),
        value_type="number",
        control="slider",
        default=2.0,
        minimum=1.0,
        maximum=5.0,
        step=0.1,
    ),
    SettingDefinition(
        key="visual_priority_enabled",
        label="Prioritize visual tracks in UI",
        description=(
            "When generating from the web UI, prefer tracks that have video assets because they "
            "are easier to review and rate while the interface is open."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="visual_priority_multiplier",
        label="Visual track boost",
        description="How much extra weight video-capable tracks receive when the UI is active.",
        value_type="number",
        control="slider",
        default=1.35,
        minimum=1.0,
        maximum=3.0,
        step=0.05,
    ),
    SettingDefinition(
        key="group_clustering_bias",
        label="Group clustering bias",
        description=(
            "Negative values emphasize variety. Positive values allow or encourage nearby songs "
            "from the same source, useful for listening through a musical consecutively."
        ),
        value_type="number",
        control="slider",
        default=0.0,
        minimum=-1.0,
        maximum=1.0,
        step=0.05,
    ),
    SettingDefinition(
        key="avoid_consecutive_compressed",
        label="Spread out compressed songs",
        description=(
            "When the library mixes lossless and lossy (compressed) audio, gently avoid playing "
            "two compressed songs back to back. Has no effect when everything is compressed."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="compressed_break_reminder",
        label="Break reminder for compressed songs",
        description=(
            "Suggest a short listening break after a run of compressed (lossy) songs, which can "
            "be more fatiguing. Conservative by default; turn off if you find it intrusive."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="loudness_warning_enabled",
        label="Loudness warnings",
        description=(
            "Watch the audio level while you listen and warn when sustained loudness looks high "
            "for your hearing. This is a relative estimate, not a calibrated dB measurement."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="loudness_warning_level",
        label="Loudness warning sensitivity",
        description=(
            "How loud (relative, 0–1) sustained playback may get before Harmonica nudges you. "
            "Lower is more cautious — the default errs toward warning early."
        ),
        value_type="number",
        control="slider",
        default=0.55,
        minimum=0.3,
        maximum=1.0,
        step=0.05,
    ),
    SettingDefinition(
        key="rating_normalization_enabled",
        label="Normalise ratings",
        description=(
            "Strip mood swings from ratings by averaging your repeat ratings and gently regressing "
            "outliers, once enough of your library is rated. Off = use your latest star as-is."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="rating_outlier_sd",
        label="Outlier tolerance",
        description=(
            "How far one rating may stray from that song's own average before it is pulled "
            "back in, measured in standard deviations. Lower is stricter."
        ),
        value_type="number",
        control="slider",
        default=1.0,
        minimum=0.25,
        maximum=3.0,
        step=0.25,
    ),
    SettingDefinition(
        key="rating_session_mood_correction",
        label="Correct session mood",
        description=(
            "Correct a whole rating session that ran uniformly generous or grumpy. Only acts once "
            "your library is well-rated."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="rating_session_min_songs",
        label="Session-mood minimum songs",
        description=(
            "Minimum songs rated in one sitting before session-mood correction can apply."
        ),
        value_type="number",
        control="stepper",
        default=10,
        minimum=5,
        maximum=50,
        step=1,
        unit="songs",
    ),
    SettingDefinition(
        key="rating_coverage_ready_fraction",
        label="Normalisation readiness",
        description=(
            "Fraction of rateable songs that must have a rating before library-wide normalisation "
            "switches on. Until then your plain averages are used as-is."
        ),
        value_type="number",
        control="slider",
        default=0.6,
        minimum=0.2,
        maximum=1.0,
        step=0.05,
    ),
    SettingDefinition(
        key="rating_calibration_enabled",
        label="Calibrate to your scale",
        description=(
            "Account for how you personally use the stars: if you tend to rate only 4–5, your "
            "average song is treated as neutral and a 4 counts as mediocre. Off = take stars at "
            "face value."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="satiation_enabled",
        label="Ease off recent favourites",
        description=(
            "Pace a song you've been playing a lot lately so it doesn't wear out, then let it "
            "recover over the following weeks. Protects against burning out on a song you love."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="satiation_strength",
        label="Ease-off strength",
        description="How strongly a recently over-played song is held back. Higher = more spacing.",
        value_type="number",
        control="slider",
        default=0.5,
        minimum=0.0,
        maximum=2.0,
        step=0.1,
    ),
    SettingDefinition(
        key="satiation_window_days",
        label="Recent-play window",
        description=(
            "Over how many days recent plays count toward easing a song off (a play this long ago "
            "counts half). Roughly your binge length."
        ),
        value_type="number",
        control="stepper",
        default=14,
        minimum=3,
        maximum=60,
        step=1,
        unit="days",
    ),
    SettingDefinition(
        key="rediscovery_enabled",
        label="Resurface dormant favourites",
        description=(
            "Gradually bring back a song you loved but haven't heard in a long time, so it returns "
            "fresh. Only applies to your above-average songs that have been played before."
        ),
        value_type="boolean",
        control="switch",
        default=True,
    ),
    SettingDefinition(
        key="rediscovery_strength",
        label="Rediscovery strength",
        description=(
            "How much extra weight a long-dormant favourite earns. Higher = returns sooner."
        ),
        value_type="number",
        control="slider",
        default=0.4,
        minimum=0.0,
        maximum=1.0,
        step=0.05,
    ),
    SettingDefinition(
        key="rediscovery_halflife_days",
        label="Rediscovery patience",
        description=(
            "How long a favourite must rest for half of its rediscovery boost. Larger = waits "
            "longer before bringing a song back."
        ),
        value_type="number",
        control="stepper",
        default=60,
        minimum=14,
        maximum=180,
        step=1,
        unit="days",
    ),
    SettingDefinition(
        key="favourite_pacing_enabled",
        label="Give favourites special pacing",
        description=(
            "For songs you have tagged as favourites, apply the ease-off and rediscovery pacing "
            "more firmly, so a favourite is rested harder after a spell of heavy play and returns "
            "sooner once it has rested. Off by default. Tag favourites in the track editor."
        ),
        value_type="boolean",
        control="switch",
        default=False,
    ),
    SettingDefinition(
        key="favourite_pacing_strength",
        label="Favourite pacing strength",
        description=(
            "How much more firmly favourites are paced. 1.0 treats them like any other song; "
            "higher spaces them out and resurfaces them more strongly."
        ),
        value_type="number",
        control="slider",
        default=1.5,
        minimum=1.0,
        maximum=3.0,
        step=0.1,
    ),
    SettingDefinition(
        key="why_show_math",
        label="Show the maths in “why this song”",
        description=(
            "Add the full calculation — every multiplier and the final score — beneath the plain "
            "explanation. The plain reasons are always shown; this just reveals the numbers."
        ),
        value_type="boolean",
        control="switch",
        default=False,
    ),
    SettingDefinition(
        key="cover_two_level_enabled",
        label="Two-level cover selection",
        description=(
            "Experimental. Pick a song first, then choose which rendition (cover) of it to play, "
            "with more-covered songs surfacing a little more often. Off by default."
        ),
        value_type="boolean",
        control="switch",
        default=False,
    ),
    SettingDefinition(
        key="cover_count_log_base",
        label="Cover-count log base",
        description=(
            "How much a song's many covers boost how often it appears. The boost is logarithmic: "
            "higher base = smaller boost. Base 4 → a song with 10 covers shows ~2.7× as often, "
            "never 10×."
        ),
        value_type="number",
        control="slider",
        default=4.0,
        minimum=1.5,
        maximum=12.0,
        step=0.5,
    ),
    SettingDefinition(
        key="cover_original_bonus",
        label="Original-rendition nudge",
        description=(
            "A small, fixed extra weight for the original recording when choosing between covers "
            "of a song. 0 = no preference; it never overrides a clearly better cover."
        ),
        value_type="number",
        control="slider",
        default=0.1,
        minimum=0.0,
        maximum=0.5,
        step=0.05,
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
