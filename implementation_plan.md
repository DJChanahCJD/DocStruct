# DocStruct Final Design Implementation Plan

## Status

- [x] Phase 1: Create this tracking document.
- [x] Phase 2: Cut over schema and DTO to `Document IR`, `Evidence`, and `BusinessView`.
- [x] Phase 3: Convert parser output into stable `DocumentElement[]` IR and persist it.
- [x] Phase 4: Add section-aware IR chunking with `[ELEMENT: ...]` markers.
- [x] Phase 5: Replace implicit Markdown extraction with `DocumentOutline + ExtractionContract + chunk markdown`.
- [x] Phase 6: Add deterministic reduce, global object IDs, evidence binding, and safe fallback.
- [x] Phase 7: Wire upload, retry, document DTO, experiment SDK, and minimal frontend types.
- [x] Phase 8: Add focused tests and run validation commands.

## File Scope

- `schemas/models.py`
- `schemas/dto.py`
- `core/ir.py`
- `core/chunker.py`
- `core/extractor.py`
- `core/utils.py`
- `core/document_service.py`
- `core/experiment_sdk.py`
- `frontend/src/lib/api.ts`
- focused tests under `tests/`

## Acceptance Commands

- `uv run python -m compileall core schemas main.py`
- `uv run python -m unittest discover`
- If needed: existing experiment runner to compare section-aware chunking and evidence coverage.

## Notes

- This is a clean cutover. No historical SQLite migration or legacy schema branch is planned.
- `parsed_content` remains the human-readable Markdown preview.
- `document_ir` is the machine-readable source for chunking and evidence binding.
