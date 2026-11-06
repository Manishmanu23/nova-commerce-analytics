# NovaCommerce pipeline. `make all` rebuilds everything from scratch.
SHELL := /bin/bash
PY    ?= python
CUSTOMERS ?= 30000
LANDING ?= data/landing
DBT   := cd dbt/nova_dbt && dbt
export PYTHONPATH := $(PWD)/python
-include .env
export


.PHONY: dashboard docs help setup db-up db-down generate ingest dbt-deps dbt-build dbt-docs analytics anomalies dq simulate \
        copilot-eval copilot-app test lint all sample ci clean

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup:           ## install python deps
	$(PY) -m pip install -e ".[dev,copilot]"

db-up:           ## start postgres in docker
	docker compose -f docker/docker-compose.yml up -d --wait

db-down:
	docker compose -f docker/docker-compose.yml down

generate:        ## synthesize source extracts (seeded, reproducible)
	$(PY) -m nova.generator.run --customers $(CUSTOMERS) --out $(LANDING)

ingest:          ## load landing files into raw.* (idempotent)
	$(PY) ingestion/load_raw.py --landing $(LANDING)

dbt-deps:
	$(DBT) deps --profiles-dir .

dbt-build: dbt-deps  ## run + test all dbt models (staging -> marts -> metrics)
	$(DBT) build --profiles-dir . ; rc=$$?; $(PY) -m nova.dq.collect_dbt_results; exit $$rc

dbt-docs:
	$(DBT) docs generate --profiles-dir . && $(DBT) docs serve --profiles-dir .

analytics:       ## statistics, experiments, segmentation, forecast
	$(PY) -m nova.analytics.run_all

anomalies:       ## anomaly detection + drilldown
	$(PY) -m nova.anomaly.run

dq:              ## data-quality scorecard
	$(PY) -m nova.dq.scorecard

simulate:        ## decision-simulator baseline + example scenario
	$(PY) -m nova.simulator.engine --example

copilot-eval:    ## run copilot grounding evaluation suite
	$(PY) -m nova.copilot.evals

copilot-app:
	streamlit run python/nova/copilot/app.py

test:            ## python unit tests
	$(PY) -m pytest -q

lint:
	ruff check python ingestion tests

all: generate ingest dbt-build dq analytics anomalies simulate copilot-eval docs dashboard  ## full pipeline

dashboard:       ## build the 6-page HTML dashboard + Power BI CSV data pack
	$(PY) -m nova.dashboard.export

docs:            ## regenerate data dictionary + README charts from the warehouse
	$(PY) -m nova.common.data_dictionary && $(PY) -m nova.common.charts

sample:          ## tiny dataset for CI
	$(PY) -m nova.generator.run --customers 1500 --session-mult 0.1 --out data/sample/landing

ci: sample       ## what GitHub Actions runs
	$(PY) ingestion/load_raw.py --landing data/sample/landing --full-refresh
	$(DBT) deps --profiles-dir . && $(DBT) build --profiles-dir . --target ci
	$(PY) -m pytest -q

clean:
	rm -rf data/landing data/ground_truth dbt/nova_dbt/target dbt/nova_dbt/logs
