# Live policy sandbox (browser, no container)

Runs the trained `haichau_rush` DQN weights live in the browser on one Hải Châu
intersection. No Docker/CityFlow at demo time.

> **Not a DQN result.** This sandbox runs the real trained weights (the JS
> forward pass is parity-tested against `SharedDQN.greedy_action` below — the
> *decisions* you see are the real policy), but it runs on a toy, hand-built
> single-intersection micro-model whose dynamics the DQN was never trained
> on. On that mismatched micro-model the DQN **under-performs**, so nothing
> quantitative you see here (queue lengths, timing, "who wins") is a DQN
> result — it is illustrative only. For the real, citable DQN result, use the
> A/B replay demo instead (`docs/demo_replay_ab.md`, `frontend/replay_ab.html`):
> DQN **−30.8%** waiting time vs Fixed-Time on the real 53-node network.

## Regenerate the model bundle
```
PYTHONPATH=src python scripts/export_sandbox_model.py --area haichau_rush --inter 420249146
# choose a different hero intersection:
PYTHONPATH=src python scripts/export_sandbox_model.py --area haichau_rush --list
PYTHONPATH=src python scripts/export_sandbox_model.py --area haichau_rush --inter <ID>
```

## Run the demo
```
python scripts/serve_replay.py --no-browser
# open http://localhost:8080/frontend/sandbox.html
```

## Tests
```
PYTHONPATH=src:. python -m pytest tests/test_export_sandbox.py -v   # export + forward mirror
node --test tests/sandbox/*.test.cjs                                # JS parity + micro-model
```

The JS parity test is the faithfulness gate: it proves the in-browser forward
pass reproduces `SharedDQN.greedy_action`, so the demo is the *real* trained policy.
It illustrates policy behavior on a micro-model; the quantitative 53-node results
are in Chapter 4.
