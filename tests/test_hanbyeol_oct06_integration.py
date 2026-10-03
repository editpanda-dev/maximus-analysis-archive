import pandas as pd

from scripts.build_hanbyeol_20261006_integration import counts_by_area


def test_unknown_entrance_does_not_become_certified_walk_access():
    routes = pd.DataFrame([
        {"area_code":"A", "place_id":"public:1", "route_status":"inside_area",
         "walk_access_400":True, "proxy_walk_access_400":True},
        {"area_code":"A", "place_id":"public:2", "route_status":"assumed_straight_entrance_connector",
         "walk_access_400":pd.NA, "proxy_walk_access_400":True},
    ])
    ids={"public:1","public:2"}
    assert counts_by_area(routes,ids,400,.25,"certified",["A","B"]).to_dict()=={"A":1.0,"B":0.0}
    assert counts_by_area(routes,ids,400,.25,"proxy",["A","B"]).to_dict()=={"A":1.25,"B":0.0}
