# Third-Party Notices

Last updated: 2026-04-15 (UTC)

This file lists direct third-party components used by this repository and their upstream licenses, based on source imports and package metadata available during audit.

## Python dependencies

| Package | Used in | Upstream license (reported) | Upstream project |
|---|---|---|---|
| openai | `Aria-autoformalizer`, `AriaScorer` | Apache-2.0 | https://github.com/openai/openai-python |
| requests | `Aria-autoformalizer`, `AriaScorer` | Apache-2.0 | https://requests.readthedocs.io |
| aiohttp | `Aria-autoformalizer` | Apache-2.0 | https://github.com/aio-libs/aiohttp |
| PyYAML | `Aria-autoformalizer` | MIT | https://pyyaml.org/ |
| pydantic | `Aria-autoformalizer` | MIT | https://github.com/pydantic/pydantic |
| loguru | `Aria-autoformalizer` | MIT | https://github.com/Delgan/loguru |
| pandas | `AriaScorer` | BSD-3-Clause | https://pandas.pydata.org |
| huggingface_hub | `AriaScorer` | Apache-2.0 | https://github.com/huggingface/huggingface_hub |
| fsspec | `AriaScorer` | BSD-3-Clause | https://github.com/fsspec/filesystem_spec |

## Vendored or in-repo components to verify

| Component | Location | Notes |
|---|---|---|
| PocketFlow-like runtime | `Aria-autoformalizer/src/PocketFlow.py` | Check provenance against upstream PocketFlow and preserve required copyright/license text if copied or modified. |

## Notes

- This repository is licensed under `Apache-2.0`; see top-level `LICENSE`.
- If you distribute binaries or Docker images, include this notice file and all required full license texts.
- Re-run a license audit whenever dependencies are changed.
