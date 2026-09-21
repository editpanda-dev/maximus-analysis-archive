from scripts.collect_kakao_study_pois import build_tiles


def test_build_tiles_covers_the_input_bounds_without_overlap_gaps():
    tiles = build_tiles((126.0, 37.0, 126.2, 37.2), columns=2, rows=2)

    assert len(tiles) == 4
    assert tiles[0] == (126.0, 37.0, 126.1, 37.1)
    assert tiles[-1] == (126.1, 37.1, 126.2, 37.2)
