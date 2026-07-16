# Live policy sandbox (browser, no container)

Runs the trained `haichau_rush` DQN weights live in the browser on one Hải Châu
intersection. No Docker/CityFlow at demo time.

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
