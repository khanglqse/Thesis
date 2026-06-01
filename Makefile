SHELL := /bin/bash
CF_IMAGE := cityflowproject/cityflow:latest
SUMO_HOME ?= /opt/homebrew/share/sumo
PWD := $(shell pwd)

# Run an arbitrary command inside the CityFlow container with the repo mounted.
# Usage: make cf-run CMD="python3 scripts/foo.py"
cf-run:
	docker run --rm -v "$(PWD)":/work -w /work $(CF_IMAGE) sh -lc '$(CMD)'

# Run pure-python unit tests locally (cityflow NOT required).
test:
	SUMO_HOME=$(SUMO_HOME) python3 -m pytest -m 'not docker' -v

# Run engine integration tests inside the CityFlow container.
cf-test:
	docker run --rm -v "$(PWD)":/work -w /work $(CF_IMAGE) \
		sh -lc 'pip install pytest pyyaml numpy >/dev/null 2>&1; python3 -m pytest -m docker -v -o addopts="" -o pythonpath=src'

# Smoke-check that cityflow imports inside the container.
cf-smoke:
	docker run --rm $(CF_IMAGE) python3 -c 'import cityflow; print("cityflow OK")'

.PHONY: cf-run test cf-test cf-smoke
