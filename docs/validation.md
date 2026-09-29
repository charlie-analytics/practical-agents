# Validation and limits

Initial release: 29 September 2026.

- Offline demos exercise all five domains with explicitly fictional fixtures.
- Unit tests cover deliberate data defects, retractions, exact decimal math, overpayments, duplicate invoice rejection, path/symlink escapes, network opt-in, forbidden tools, invalid arguments, budget exhaustion and model-observation flow.
- The runner is tested with scripted model responses. These tests validate control flow; they do not measure a language model's reasoning, accuracy or robustness.
- Live model evaluation is not included. No Ollama model was installed on the build machine, and no paid inference calls were made for this project.
- Continuous integration is configured for Python 3.10, 3.12 and 3.13. The initial local run uses Python 3.9.6; inspect GitHub Actions for remote results.

The five agents are runnable prototypes. Before using one with real operational data, review the trace and verify the answer against the deterministic tool result. An LLM can still misread correct tool evidence. No professional certification, benchmark score, production reliability or time saving is implied by these tests.

Social tests cover missing context, account mismatch, nonexistent citations, expanded context and draft fingerprints. Media tests cover multi-source edit timing, non-finite/out-of-range cuts, unknown assets and invalid canvases. The tests do not establish vision or transcription quality.

A private, assistant-directed integration pilot prepared a real 22.68-second input and rendered eight cuts from three local videos into a 24-second, 864-by-1080 montage. FFmpeg decoded the result and sampled output frames were inspected. A separate private finishing script added titles and an original procedural instrumental. The public renderer supports explicit cuts, 4:5 cover crops, focus positions and a modest gym contrast preset. This verifies media plumbing, not autonomous story selection, music quality, full playback review or publishing. Source footage and personal output are excluded from this repository. Some iCloud source files needed time to download before they could be read; a catalogue entry is not evidence of immediate local availability.

## Reproduce

```bash
python3 -m unittest discover -s tests -v
python3 -m agentkit all --demo --output runs/demo-results.json
```

For a real model evaluation, record model/version, task, source-file hashes, full trace, expected findings and failure cases. Keep that evaluation separate from the existing Hugging Face course score, which belongs to another project.
