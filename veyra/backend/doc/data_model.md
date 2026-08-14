# Normalized Data Model

## GenomicRecord

The core data structure. All parsers produce `GenomicRecord` instances.

| Field         | Type                   | Description                                      |
|---------------|------------------------|--------------------------------------------------|
| `id`          | `str`                  | Sequence/record identifier                       |
| `sequence`    | `str`                  | Nucleotide sequence (uppercased)                 |
| `length`      | `int`                  | Sequence length in bases                         |
| `description` | `str`                  | Full header/description text                     |
| `accession`   | `str \| None`          | Accession number                                 |
| `annotations` | `dict[str, Any]`       | Key-value metadata (GenBank source, etc.)        |
| `features`    | `list[GenomicFeature]` | Annotated features (gene, CDS, source, etc.)     |
| `coordinate`  | `GenomicCoordinate`    | Genomic coordinates of the record                |
| `quality`     | `QualityData`          | FASTQ quality scores (None for other formats)    |
| `provenance`  | `Provenance`           | Source file, format, parser info                 |
| `validation`  | `ValidationResult`     | Validation status, errors, warnings              |

## GenomicFeature

Represents a single annotated feature within a record.

| Field        | Type                   | Description                    |
|--------------|------------------------|--------------------------------|
| `type`       | `str`                  | Feature type (gene, CDS, etc.) |
| `location`   | `GenomicCoordinate`    | Feature coordinates            |
| `qualifiers` | `dict[str, list[str]]` | Feature qualifiers/attributes  |

## GenomicCoordinate

| Field      | Type              | Description                        |
|------------|-------------------|------------------------------------|
| `start`    | `int \| None`     | 0-based start position             |
| `end`      | `int \| None`     | End position (exclusive)           |
| `strand`   | `int \| None`     | 1=forward, -1=reverse, 0=unknown  |
| `scaffold` | `str \| None`     | Chromosome/scaffold name           |
| `assembly` | `str \| None`     | Assembly version                   |

## QualityData

| Field           | Type            | Description              |
|-----------------|-----------------|--------------------------|
| `scores`        | `list[int]`     | Per-base Phred scores    |
| `mean_quality`  | `float \| None` | Mean Phred quality       |
| `min_quality`   | `int \| None`   | Minimum Phred quality    |
| `max_quality`   | `int \| None`   | Maximum Phred quality    |

## Provenance

| Field               | Type          | Description                    |
|---------------------|---------------|--------------------------------|
| `source_filename`   | `str`         | Original input filename        |
| `input_format`      | `VEYRAFormat` | Detected format                |
| `parser_name`       | `str`         | Parser identifier              |
| `parser_version`    | `str`         | Parser version                 |
| `database_source`   | `str \| None` | NCBI/database source info      |
| `accession`         | `str \| None` | Accession from source          |
| `assembly_version`  | `str \| None` | Assembly version               |

## ValidationResult

| Field      | Type           | Description              |
|------------|----------------|--------------------------|
| `is_valid` | `bool`         | True if no errors found  |
| `errors`   | `list[str]`    | Blocking errors          |
| `warnings` | `list[str]`    | Non-blocking warnings    |
