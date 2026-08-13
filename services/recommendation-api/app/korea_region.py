"""Explicit product policy for supported South Korean origin regions."""

from dataclasses import dataclass


Point = tuple[float, float]


@dataclass(frozen=True)
class SupportedRegion:
    name: str
    polygon: tuple[Point, ...]


# This is a product service-area policy, not a claim of cadastral precision.
# It covers the South Korean mainland/nearshore area and the principal inhabited
# or administratively significant outlying islands. Keeping the regions explicit
# makes foreign in-box coordinates (notably Tsushima) auditable and testable.
SUPPORTED_SOUTH_KOREA_REGIONS = (
    SupportedRegion(
        name="mainland_and_nearshore_islands",
        polygon=(
            (126.40, 37.78),
            (126.70, 37.82),
            (126.98, 37.96),
            (127.08, 38.15),
            (127.30, 38.24),
            (127.55, 38.34),
            (127.85, 38.30),
            (128.10, 38.35),
            (128.35, 38.42),
            (128.65, 38.60),
            (129.35, 38.45),
            (129.55, 38.05),
            (129.60, 37.15),
            (129.55, 36.05),
            (129.40, 35.35),
            (129.25, 34.85),
            (128.55, 34.55),
            (127.70, 34.30),
            (126.70, 34.10),
            (125.70, 34.30),
            (125.65, 35.10),
            (125.85, 36.10),
            (126.05, 37.10),
            (126.00, 38.20),
        ),
    ),
    SupportedRegion(
        name="jeju_and_marado",
        polygon=(
            (126.05, 33.05),
            (126.98, 33.05),
            (127.02, 33.68),
            (126.05, 33.68),
            (126.05, 33.05),
        ),
    ),
    SupportedRegion(
        name="baengnyeong_and_daecheong",
        polygon=(
            (124.50, 37.75),
            (124.82, 37.75),
            (124.82, 38.08),
            (124.50, 38.08),
            (124.50, 37.75),
        ),
    ),
    SupportedRegion(
        name="yeonpyeong",
        polygon=(
            (125.55, 37.55),
            (125.85, 37.55),
            (125.85, 37.85),
            (125.55, 37.85),
            (125.55, 37.55),
        ),
    ),
    SupportedRegion(
        name="heuksan_and_hongdo",
        polygon=(
            (125.00, 34.25),
            (125.75, 34.25),
            (125.75, 35.05),
            (125.00, 35.05),
            (125.00, 34.25),
        ),
    ),
    SupportedRegion(
        name="ulleungdo",
        polygon=(
            (130.75, 37.35),
            (131.05, 37.35),
            (131.05, 37.65),
            (130.75, 37.65),
            (130.75, 37.35),
        ),
    ),
    SupportedRegion(
        name="dokdo",
        polygon=(
            (131.80, 37.18),
            (131.93, 37.18),
            (131.93, 37.31),
            (131.80, 37.31),
            (131.80, 37.18),
        ),
    ),
)


def is_south_korea_coordinate(*, latitude: float, longitude: float) -> bool:
    """Return whether WGS84 coordinates are in the supported Korea regions."""
    return any(
        _point_in_polygon(longitude, latitude, region.polygon)
        for region in SUPPORTED_SOUTH_KOREA_REGIONS
    )


def _point_in_polygon(x: float, y: float, polygon: tuple[Point, ...]) -> bool:
    inside = False
    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        if _point_on_segment(
            x, y, previous_x, previous_y, current_x, current_y
        ):
            return True
        crosses_ray = (current_y > y) != (previous_y > y)
        if crosses_ray:
            intersection_x = (
                (previous_x - current_x)
                * (y - current_y)
                / (previous_y - current_y)
                + current_x
            )
            if x < intersection_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _point_on_segment(
    x: float,
    y: float,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> bool:
    cross_product = (x - start_x) * (end_y - start_y) - (
        y - start_y
    ) * (end_x - start_x)
    if abs(cross_product) > 1e-10:
        return False
    return (
        min(start_x, end_x) - 1e-10 <= x <= max(start_x, end_x) + 1e-10
        and min(start_y, end_y) - 1e-10
        <= y
        <= max(start_y, end_y) + 1e-10
    )
