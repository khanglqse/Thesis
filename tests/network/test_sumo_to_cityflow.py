from traffic_rl.network.sumo_to_cityflow import build_converter_docker_command


def test_converter_command_mounts_repo_and_calls_converter():
    cmd = build_converter_docker_command(
        "data/sumo/danang_subarea.net.xml",
        "data/danang/roadnet_subarea.json",
        image="cityflowproject/cityflow:latest",
        workdir="/work",
    )
    joined = " ".join(cmd)
    assert cmd[0] == "docker"
    assert "run" in cmd and "--rm" in cmd
    assert "/work" in joined
    assert "pip install" in joined
    assert "sympy" in joined and "traci" in joined and "sumolib" in joined
    assert "/home/cityflow/tools/converter/converter.py" in joined
    assert "--sumonet data/sumo/danang_subarea.net.xml" in joined
    assert "--cityflownet data/danang/roadnet_subarea.json" in joined
