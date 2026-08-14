# Development Guide

## Setup

```bash
cd /home/hrirake/Desktop/hck15/veyra/backend
pip install -r requirements.txt
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with unittest
python -m unittest discover tests/ -v

# Run a specific test class
python -m unittest tests.test_ingestion.TestFastaParser -v
```

## Project Layout

- `parsers/` – Add new format parsers here
- `schemas/` – Data model definitions (extend with new dataclasses as needed)
- `services/` – Orchestration logic (pipeline stages)
- `utils/` – Shared utilities
- `tests/` – Unit tests with fixtures

## Adding a New Parser

1. Create `parsers/newformat_parser.py` with a `parse(filepath) -> Iterator[GenomicRecord]` function
2. Register the format in `schemas/genomic_record.py` (`VEYRAFormat` enum)
3. Add extension mappings in `parsers/detector.py`
4. Add content detection rules in `parsers/detector.py`
5. Register the parser in `services/ingestion.py`
6. Add tests in `tests/test_ingestion.py`

## Code Conventions

- Python 3.10+ with type hints throughout
- Dataclasses for structured data (not Pydantic in v0.1)
- Biopython for all biological format parsing
- No global mutable state
- Structured error handling with custom exceptions
- Each module is independently testable

## Adding New Tests

1. Create small fixture files in `tests/fixtures/`
2. Add test methods to `tests/test_ingestion.py`
3. Test both success and error paths
4. Test multi-record and edge cases
