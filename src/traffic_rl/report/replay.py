"""Truncate a CityFlow replay log to the first N timesteps.

Each line of a CityFlow ``replayLogFile`` is one simulation step, so keeping the
first N lines yields a valid, much smaller replay the WebGL frontend can load.
Streaming line-by-line keeps memory flat even for ~760 MB inputs.
"""


def truncate_replay(src_path, dst_path, n_steps):
    """Copy the first ``n_steps`` lines of ``src_path`` into ``dst_path``.

    Returns the number of lines actually written (``<= n_steps``).
    """
    written = 0
    with open(src_path) as src, open(dst_path, "w") as dst:
        for line in src:
            if written >= n_steps:
                break
            dst.write(line)
            written += 1
    return written
