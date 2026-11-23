# v0.1.0 — Runnable theory of a science data flywheel

HELIX v0.1.0 is a local, evidence-first AI4Science data-flywheel reference
implementation.

## Included

- Python and SQLite ingestion, provenance, split isolation, task generation,
  verification, export, and evaluation feedback.
- Local Web workspace for assets, synthesis, quality gates, and feedback.
- arXiv and Crossref metadata connectors.
- CSV, FASTA, XYZ, and ASCII STL baseline extractors.
- RL, SFT, and DPO JSONL export contracts.
- Original CC0 fixtures and 25 automated tests.
- Chinese handbook, data card, API documentation, strategy mapping, and an
  evidence-based verification report.

## Verified release behavior

- 25/25 automated tests pass on Python 3.9.6.
- A clean synthetic run creates 56 tasks; 36 pass all gates and 20 are
  quarantined or held out.
- RL, SFT, and DPO fixture exports each contain 36 validated records.
- arXiv and Crossref metadata retrieval and an actual remote CC0 CSV download
  were verified on 2026-11-23.

## Boundaries

This release does not claim end-to-end scientific multimodal understanding,
completed RL model training, or measured model improvement. Real model
generation requires a configured compatible provider. Production deployment
requires authentication, persistent job infrastructure, quotas, and stronger
network isolation.
