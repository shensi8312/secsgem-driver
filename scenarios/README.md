# Starter GEM E30-Style Scenarios

These are local starter scenarios for integration evaluation. They are not a
production conformance suite.

Implemented in `demo/run.py` and tested in `tests/test_gateway_scenarios.py`:

1. Communication establishment: host request -> `S1F14` reply.
2. Status-variable read: legacy status line -> `S1F4` SVID values.
3. Alarm report: simulated interlock -> `S5F1` alarm body.
4. Remote command reply: host command -> `S2F42` acknowledgement.
5. Event report: mapped snapshot -> `S6F11` report body.

Roadmap items should stay labeled as planned until implemented.
