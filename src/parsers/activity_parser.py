"""Parse Magic Eden collection activity responses."""

from __future__ import annotations

from typing import Any

from src.models.dataclasses import Pull
from src.parsers.pull_parser import parse_me_activity


def parse_collection_activities(
    activities: list[dict[str, Any]],
    pack_type: str = "",
) -> list[Pull]:
    """Parse a list of ME v2 collection activities into Pull objects.

    Filters for relevant activity types (purchases/mints, not listings).
    """
    pulls = []
    for activity in activities:
        # Filter for relevant types
        activity_type = activity.get("type", "")
        if activity_type in ("list", "delist", "cancelBid"):
            continue

        pull = parse_me_activity(activity, pack_type)
        if pull is not None:
            pulls.append(pull)

    return pulls
