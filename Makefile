SHELL := /bin/bash
CF_IMAGE := cityflowproject/cityflow:latest
SUMO_HOME ?= /opt/homebrew/share/sumo

# Run an arbitrary command inside the CityFlow container with the repo mounted.
# Usage: make cf-run CMD="python3 scripts/foo.py"
cf-run:
	@test -n "$(CMD)" || { echo 'Usage: make cf-run CMD="..."'; exit 1; }
	docker run --rm -v "$(CURDIR)":/work -w /work $(CF_IMAGE) sh -lc '$(CMD)'

# Run pure-python unit tests locally (cityflow NOT required).
test:
	SUMO_HOME=$(SUMO_HOME) python3 -m pytest -m 'not docker' -v

# Run engine integration tests inside the CityFlow container.
cf-test:
	docker run --rm -v "$(CURDIR)":/work -w /work $(CF_IMAGE) \
		sh -lc 'pip install pytest pyyaml numpy dataclasses >/dev/null 2>&1; python3 -m pytest -m docker -v -o addopts="" -o pythonpath=src --ignore=tests/network --continue-on-collection-errors'

# Smoke-check that cityflow imports inside the container.
cf-smoke:
	docker run --rm $(CF_IMAGE) python3 -c 'import cityflow; print("cityflow OK")'

LEARNING_SEED ?=
HAICHAU_IMAGE ?= traffic-rl-cityflow-research:v2

haichau-train-smoke:
	@test -n "$(LEARNING_SEED)" || { echo 'LEARNING_SEED is required'; exit 1; }
	docker run --rm --platform linux/amd64 -v "$(CURDIR)":/work -w /work \
		$(HAICHAU_IMAGE) python3 scripts/train_haichau_network.py \
		--mode smoke --learning-seed $(LEARNING_SEED)

haichau-train-pilot:
	@test -n "$(LEARNING_SEED)" || { echo 'LEARNING_SEED is required'; exit 1; }
	docker run --rm --platform linux/amd64 -v "$(CURDIR)":/work -w /work \
		$(HAICHAU_IMAGE) python3 scripts/train_haichau_network.py \
		--mode pilot --learning-seed $(LEARNING_SEED)

.PHONY: cf-run test cf-test cf-smoke haichau-train-smoke haichau-train-pilot
