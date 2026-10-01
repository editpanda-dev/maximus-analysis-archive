# Local Transit Accessibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace quota-limited ODsay calls with a reproducible local 30-minute public-transit accessibility pipeline and a Colab runner.

**Architecture:** Validate a standard GTFS feed, calculate earliest-arrival reachability from each Dongdaemun origin with scheduled transit and explicit walking transfers, then spatially join reachable stops to Seoul administrative dongs. Keep routing outputs separate from the existing ODsay cache.

**Tech Stack:** Python 3, pandas, GeoPandas, standard GTFS CSV/ZIP, Jupyter/Colab

**Spec:** `docs/odsay_30min_pipeline.md`

## Global Constraints

- Total travel-time cutoff is 1,800 seconds.
- Walking and transfers count toward the cutoff.
- Administrative-dong boundaries, not legal-dong boundaries, define destinations.
- Existing ODsay caches and user data are not overwritten.

---

### Task 1: GTFS validation and scheduled routing core

**Files:**
- Create: `scripts/local_transit_accessibility.py`
- Create: `tests/test_local_transit_accessibility.py`

**Interfaces:**
- Consumes: GTFS directory or ZIP and origin CSV.
- Produces: `parse_gtfs_time`, `validate_gtfs`, and earliest-arrival stop records.

- [ ] Write tests for GTFS times over 24 hours, required-file validation, direct rides, transfers, and cutoff exclusion.
- [ ] Run the tests and confirm failure because the module does not exist.
- [ ] Implement the minimum scheduled connection-scan router with walking access and transfer edges.
- [ ] Run the focused and full test suites.

### Task 2: Destination aggregation and command-line execution

**Files:**
- Modify: `scripts/local_transit_accessibility.py`
- Test: `tests/test_local_transit_accessibility.py`

**Interfaces:**
- Consumes: reachable stop records and `seoul_administrative_dongs_20260701.geojson`.
- Produces: origin-stop pairs, origin-dong pairs, and aggregated reachable-dong CSV files.

- [ ] Write a failing test for coordinate-based origin access and destination output schema.
- [ ] Implement CLI input/output and the administrative-dong spatial join.
- [ ] Verify tests and run `--check-feed` against a fixture.

### Task 3: Colab handoff

**Files:**
- Create: `notebooks/local_transit_30min_colab.ipynb`
- Create: `docs/local_transit_30min_colab.md`
- Create: `requirements-local-transit.txt`

**Interfaces:**
- Consumes: project folder, a GTFS ZIP, origins CSV, administrative-dong GeoJSON.
- Produces: the same processed CSV outputs as local execution.

- [ ] Add Drive-mount/upload, dependency installation, input audit, routing, and download cells.
- [ ] Add a plain-language checklist separating prepared inputs from the one missing GTFS feed.
- [ ] Validate notebook JSON and execute its non-Colab Python logic locally.
