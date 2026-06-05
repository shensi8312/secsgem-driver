# Gateway Demo Minimum Spec

This repo is suitable for a public product-page GitHub link only if it remains:

- runnable with one command
- honest about early/v0 status
- free of fabricated traction or production claims
- clear that production work needs equipment-specific mapping and validation

## Acceptance Standard

A stranger can clone the repo, run:

```bash
python demo/run.py
```

and see a deterministic local chain:

1. HSMS/GEM-style communication establishment (`S1F14` response)
2. SVID read (`S1F4`)
3. alarm report (`S5F1`)
4. remote command reply (`S2F42`)
5. event report (`S6F11`)

The expected console output is committed in:

- `demo/expected_output.txt`

## Honesty Rules

Do not add:

- download counts
- contributor counts
- customer/country counts
- production-tested / production-ready claims
- universal equipment support claims
- GEM compliance guarantees
- competitor or customer names as implied support

Use:

- early / v0
- simulator work
- integration evaluation
- scoped integration review
- equipment-specific validation
- customer acceptance testing
