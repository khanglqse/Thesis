from traffic_rl.network.osm_to_sumo import build_netconvert_command


def test_command_includes_osm_input_and_output():
    cmd = build_netconvert_command("in.osm.xml", "out.net.xml", tls_default_type="actuated")
    assert cmd[0] == "netconvert"
    assert "--osm-files" in cmd
    assert cmd[cmd.index("--osm-files") + 1] == "in.osm.xml"
    assert "--output-file" in cmd
    assert cmd[cmd.index("--output-file") + 1] == "out.net.xml"


def test_command_imports_and_joins_traffic_lights():
    cmd = build_netconvert_command("in.osm.xml", "out.net.xml", tls_default_type="actuated")
    assert "--tls.guess-signals" in cmd
    assert "--junctions.join" in cmd
    assert "--tls.default-type" in cmd
    assert cmd[cmd.index("--tls.default-type") + 1] == "actuated"
