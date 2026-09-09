from pathlib import Path


RELEASE_IMAGE = (
    "traffic-rl-cityflow-research@sha256:"
    "8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517"
)
RELEASE_IMAGE_ID = (
    "sha256:8a946185be9dfcdfb7bd189b88b73d84bb95e5d85c3003a7432ce9369dfc0517"
)
RELEASE_DOCKERFILE_SHA256 = (
    "7464817a4fb91980e5711ce2eac96e749cecd9fc4bad6b41c1a996f0ebe11adf"
)


def test_incident_regression_target_uses_exact_release_image_and_test():
    makefile = Path("Makefile").read_text()

    assert "HAICHAU_RELEASE_IMAGE := %s" % RELEASE_IMAGE in makefile
    assert "HAICHAU_RELEASE_IMAGE_ID := %s" % RELEASE_IMAGE_ID in makefile
    assert "HAICHAU_RELEASE_DOCKERFILE_SHA256 := %s" % (
        RELEASE_DOCKERFILE_SHA256) in makefile
    assert "haichau-robustness-incident-test:" in makefile
    assert "$(HAICHAU_RELEASE_IMAGE)" in makefile
    assert "tests/sim/test_robustness_incident_docker.py" in makefile
    assert "org.traffic_rl.base_image_digest" in makefile
    assert "org.traffic_rl.dockerfile_sha256" in makefile
