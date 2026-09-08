SHELL := /bin/bash
CF_IMAGE := cityflowproject/cityflow:latest
HAICHAU_IMAGE := traffic-rl-cityflow-research:v2
HAICHAU_RELEASE_IMAGE := traffic-rl-cityflow-research@sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517
HAICHAU_RELEASE_IMAGE_ID := sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517
HAICHAU_RELEASE_DOCKERFILE_SHA256 := 7464817a4fb91980e5711ce2eac96e749cecd9fc4bad6b41c1a996f0ebe11adf
HAICHAU_PLATFORM := linux/amd64
HAICHAU_BASE_DIGEST := sha256:b57e1f0953d55384d9fadfec21148312653cf120a0b600a34e364aa2777e2e32
HAICHAU_DOCKERFILE_SHA256 := $(shell shasum -a 256 docker/cityflow-research/Dockerfile | awk '{print $$1}')
SUMO_HOME ?= /opt/homebrew/share/sumo

# Run an arbitrary command inside the CityFlow container with the repo mounted.
# Usage: make cf-run CMD="python3 scripts/foo.py"
cf-run:
	@test -n "$(CMD)" || { echo 'Usage: make cf-run CMD="..."'; exit 1; }
	docker run --rm -v "$(CURDIR)":/work -w /work $(CF_IMAGE) sh -lc '$(CMD)'

# Run pure-python unit tests locally (cityflow NOT required).
test:
	SUMO_HOME=$(SUMO_HOME) python3 -m pytest -m 'not docker and not docker_host' -v

# Run engine integration tests inside the CityFlow container.
cf-test:
	docker run --rm -v "$(CURDIR)":/work -w /work $(CF_IMAGE) \
		sh -lc 'pip install pytest pyyaml numpy dataclasses >/dev/null 2>&1; python3 -m pytest -m docker -v -o addopts="" -o pythonpath=src --ignore=tests/network --continue-on-collection-errors'

# Smoke-check that cityflow imports inside the container.
cf-smoke:
	docker run --rm $(CF_IMAGE) python3 -c 'import cityflow; print("cityflow OK")'

# Build the digest-pinned Python 3.6 CityFlow research runtime.
haichau-image:
	docker build --platform $(HAICHAU_PLATFORM) \
		--label org.traffic_rl.base_image_digest=$(HAICHAU_BASE_DIGEST) \
		--label org.traffic_rl.dockerfile_sha256=$(HAICHAU_DOCKERFILE_SHA256) \
		-t $(HAICHAU_IMAGE) docker/cityflow-research
	@test "$$(docker image inspect --format '{{ index .Config.Labels "org.traffic_rl.base_image_digest" }}' $(HAICHAU_IMAGE))" = "$(HAICHAU_BASE_DIGEST)"
	@test "$$(docker image inspect --format '{{ index .Config.Labels "org.traffic_rl.dockerfile_sha256" }}' $(HAICHAU_IMAGE))" = "$(HAICHAU_DOCKERFILE_SHA256)"
	@test "$$(docker image inspect --format '{{.Os}}/{{.Architecture}}' $(HAICHAU_IMAGE))" = "$(HAICHAU_PLATFORM)"

# Verify hashes/contracts, then run a real 60-second Fixed-Time episode.
haichau-smoke: haichau-image
	@image_id="$$(docker image inspect --format '{{.Id}}' $(HAICHAU_IMAGE))"; \
	base_digest="$$(docker image inspect --format '{{ index .Config.Labels "org.traffic_rl.base_image_digest" }}' $(HAICHAU_IMAGE))"; \
	dockerfile_sha="$$(docker image inspect --format '{{ index .Config.Labels "org.traffic_rl.dockerfile_sha256" }}' $(HAICHAU_IMAGE))"; \
	docker run --rm --platform $(HAICHAU_PLATFORM) -v "$(CURDIR):/work" -w /work \
		-e HAICHAU_DERIVED_IMAGE_ID="$$image_id" \
		-e HAICHAU_BASE_IMAGE_DIGEST="$$base_digest" \
		-e HAICHAU_DOCKERFILE_SHA256="$$dockerfile_sha" \
		-e HAICHAU_IMAGE_PLATFORM="$(HAICHAU_PLATFORM)" \
		$(HAICHAU_IMAGE) python3 scripts/verify_haichau_foundation.py --engine-smoke

# Run the lane-restriction regression only in the immutable release runtime.
haichau-robustness-incident-test:
	@test "$(HAICHAU_DOCKERFILE_SHA256)" = "$(HAICHAU_RELEASE_DOCKERFILE_SHA256)"
	@test "$$(docker image inspect --format '{{.Id}}' $(HAICHAU_RELEASE_IMAGE))" = "$(HAICHAU_RELEASE_IMAGE_ID)"
	@test "$$(docker image inspect --format '{{ index .Config.Labels "org.traffic_rl.base_image_digest" }}' $(HAICHAU_RELEASE_IMAGE))" = "$(HAICHAU_BASE_DIGEST)"
	@test "$$(docker image inspect --format '{{ index .Config.Labels "org.traffic_rl.dockerfile_sha256" }}' $(HAICHAU_RELEASE_IMAGE))" = "$(HAICHAU_RELEASE_DOCKERFILE_SHA256)"
	@docker image inspect --format 'runtime_image=$(HAICHAU_RELEASE_IMAGE) runtime_image_id={{.Id}} base_image_digest={{ index .Config.Labels "org.traffic_rl.base_image_digest" }} dockerfile_sha256={{ index .Config.Labels "org.traffic_rl.dockerfile_sha256" }}' $(HAICHAU_RELEASE_IMAGE)
	docker run --rm --platform $(HAICHAU_PLATFORM) -v "$(CURDIR):/work" -w /work \
		$(HAICHAU_RELEASE_IMAGE) sh -lc \
		'pip install pytest >/dev/null 2>&1 && python3 -m pytest -q -o addopts="" -o pythonpath=src -m docker_release tests/sim/test_robustness_incident_docker.py'
LEARNING_SEED ?=
HAICHAU_BASELINE_TUNING_ARTIFACT ?= results/haichau_network_v2/training/final-baseline-tuning.json
HAICHAU_FINAL_CONCURRENCY ?= 2
HAICHAU_BASELINE_SHARD_CONCURRENCY ?= 2
HAICHAU_SCHEDULE_SELECTION ?= results/haichau_network_v2/training/pilot-v3-schedule-selection.json

haichau-foundation-verify: haichau-image
	docker run --rm --platform $(HAICHAU_PLATFORM) -v "$(CURDIR)":/work -w /work \
		$(HAICHAU_IMAGE) python3 scripts/verify_haichau_foundation.py

haichau-train-smoke: haichau-foundation-verify
	@test -n "$(LEARNING_SEED)" || { echo 'LEARNING_SEED is required'; exit 1; }
	docker run --rm --platform $(HAICHAU_PLATFORM) -v "$(CURDIR)":/work -w /work \
		$(HAICHAU_IMAGE) python3 scripts/train_haichau_network.py \
		--mode smoke --learning-seed $(LEARNING_SEED)

haichau-train-pilot: haichau-foundation-verify
	@test -n "$(LEARNING_SEED)" || { echo 'LEARNING_SEED is required'; exit 1; }
	docker run --rm --platform $(HAICHAU_PLATFORM) -v "$(CURDIR)":/work -w /work \
		$(HAICHAU_IMAGE) python3 scripts/train_haichau_network.py \
		--mode pilot --learning-seed $(LEARNING_SEED)

haichau-train-legacy-smoke: haichau-foundation-verify
	@test -n "$(LEARNING_SEED)" || { echo 'LEARNING_SEED is required'; exit 1; }
	docker run --rm --platform $(HAICHAU_PLATFORM) -v "$(CURDIR)":/work -w /work \
		$(HAICHAU_IMAGE) python3 scripts/train_haichau_network.py \
		--controller-family shared_ddqn_legacy \
		--mode smoke --learning-seed $(LEARNING_SEED)

haichau-train-legacy-pilot: haichau-foundation-verify
	@test -n "$(LEARNING_SEED)" || { echo 'LEARNING_SEED is required'; exit 1; }
	docker run --rm --platform $(HAICHAU_PLATFORM) -v "$(CURDIR)":/work -w /work \
		$(HAICHAU_IMAGE) python3 scripts/train_haichau_network.py \
		--controller-family shared_ddqn_legacy \
		--mode pilot --learning-seed $(LEARNING_SEED)

# Produce the single validation-only tuning artifact consumed by all final runs.
haichau-precompute-final-baseline: haichau-foundation-verify
	python3 scripts/run_haichau_baseline_shards.py \
		--artifact $(HAICHAU_BASELINE_TUNING_ARTIFACT) \
		--max-concurrency $(HAICHAU_BASELINE_SHARD_CONCURRENCY)

# Launch the selected neighbor DDQN for confirmatory seeds 12--16; verified jobs are skipped.
haichau-train-final-campaign: haichau-foundation-verify
	@test -f "$(HAICHAU_BASELINE_TUNING_ARTIFACT)" || { echo 'Run make haichau-precompute-final-baseline first'; exit 1; }
	@test -f "$(HAICHAU_SCHEDULE_SELECTION)" || { echo 'Run make haichau-select-schedule-pilot first'; exit 1; }
	python3 scripts/run_haichau_final_training.py \
		--baseline-tuning-artifact $(HAICHAU_BASELINE_TUNING_ARTIFACT) \
		--pilot-schedule-selection $(HAICHAU_SCHEDULE_SELECTION) \
		--max-concurrency $(HAICHAU_FINAL_CONCURRENCY)

# Select the validation-eligible V3 schedule arm before any final training starts.
haichau-select-schedule-pilot:
	PYTHONPATH=src python3 scripts/select_haichau_pilot_schedule.py

haichau-final-training-test:
	SUMO_HOME=$(SUMO_HOME) python3 -m pytest tests/scripts/test_run_haichau_final_training.py -v

haichau-baseline-shards-test:
	SUMO_HOME=$(SUMO_HOME) python3 -m pytest tests/scripts/test_run_haichau_baseline_shards.py -v

.PHONY: cf-run test cf-test cf-smoke haichau-image haichau-smoke haichau-robustness-incident-test \
	haichau-foundation-verify haichau-train-smoke haichau-train-pilot haichau-train-final \
	haichau-train-legacy-smoke haichau-train-legacy-pilot haichau-train-legacy-final \
	haichau-precompute-final-baseline haichau-select-schedule-pilot haichau-train-final-campaign \
	haichau-final-training-test haichau-baseline-shards-test
