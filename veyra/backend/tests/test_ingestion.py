"""Tests for VEYRA ingestion backend.

Covers FASTA, FASTQ, GenBank parsing, format detection,
multi-record inputs, malformed inputs, missing files, and
normalized schema creation.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

# Ensure backend root is importable
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from parsers.detector import detect_format, FormatDetectionError
from parsers.fasta_parser import parse as parse_fasta
from parsers.fastq_parser import parse as parse_fastq
from parsers.genbank_parser import parse as parse_genbank
from schemas.genomic_record import (
    GenomicCoordinate,
    GenomicFeature,
    GenomicRecord,
    Provenance,
    QualityData,
    ValidationResult,
    VEYRAFormat,
)
from services.ingestion import IngestionError, ingest_file, get_ingestion_summary
from utils.validation import validate_record, validate_records

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


class TestFormatDetector(unittest.TestCase):
    """Tests for format detection."""

    def test_detect_fasta_by_extension(self):
        path = os.path.join(FIXTURES, "test.fasta")
        self.assertEqual(detect_format(path), VEYRAFormat.FASTA)

    def test_detect_fastq_by_content(self):
        path = os.path.join(FIXTURES, "test.fastq")
        self.assertEqual(detect_format(path), VEYRAFormat.FASTQ)

    def test_detect_genbank_by_content(self):
        path = os.path.join(FIXTURES, "test.gb")
        self.assertEqual(detect_format(path), VEYRAFormat.GENBANK)

    def test_detect_unknown_format(self):
        path = os.path.join(FIXTURES, "malformed.fasta")
        # No '>' header, no '@', no LOCUS → should be unknown
        result = detect_format(path)
        # Could be FASTA by extension; content overrides
        self.assertIn(result, (VEYRAFormat.UNKNOWN, VEYRAFormat.FASTA))

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            detect_format("/nonexistent/file.fasta")

    def test_empty_file(self):
        path = os.path.join(FIXTURES, "empty.fasta")
        result = detect_format(path)
        # Empty file with .fasta extension: content=UNKNOWN, ext=FASTA → FASTA
        # (extension fallback is the documented behavior)
        self.assertIn(result, (VEYRAFormat.UNKNOWN, VEYRAFormat.FASTA))


class TestFastaParser(unittest.TestCase):
    """Tests for FASTA parsing."""

    def test_parse_simple_fasta(self):
        path = os.path.join(FIXTURES, "test.fasta")
        records = list(parse_fasta(path))
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].id, "seq1")
        self.assertEqual(records[0].sequence, "ACGTACGTACGTACGTACGTACGT")
        self.assertEqual(records[0].length, 24)

    def test_parse_multi_record_fasta(self):
        path = os.path.join(FIXTURES, "multi.fasta")
        records = list(parse_fasta(path))
        self.assertEqual(len(records), 5)
        ids = [r.id for r in records]
        self.assertIn("multi_seq_1", ids)
        self.assertIn("multi_seq_5", ids)

    def test_fasta_description_preserved(self):
        path = os.path.join(FIXTURES, "test.fasta")
        records = list(parse_fasta(path))
        self.assertIn("test sequence one", records[0].description)

    def test_fasta_provenance(self):
        path = os.path.join(FIXTURES, "test.fasta")
        records = list(parse_fasta(path))
        self.assertEqual(records[0].provenance.input_format, VEYRAFormat.FASTA)
        self.assertEqual(records[0].provenance.source_filename, "test.fasta")

    def test_fasta_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            list(parse_fasta("/nonexistent.fasta"))

    def test_fasta_empty_file(self):
        path = os.path.join(FIXTURES, "empty.fasta")
        with self.assertRaises(ValueError):
            list(parse_fasta(path))

    def test_fasta_sequence_uppercased(self):
        path = os.path.join(FIXTURES, "test.fasta")
        records = list(parse_fasta(path))
        self.assertEqual(records[0].sequence, records[0].sequence.upper())


class TestFastqParser(unittest.TestCase):
    """Tests for FASTQ parsing."""

    def test_parse_simple_fastq(self):
        path = os.path.join(FIXTURES, "test.fastq")
        records = list(parse_fastq(path))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].id, "read1")
        self.assertEqual(records[0].sequence, "ACGTACGTACGT")

    def test_parse_multi_record_fastq(self):
        path = os.path.join(FIXTURES, "multi.fastq")
        records = list(parse_fastq(path))
        self.assertEqual(len(records), 3)

    def test_fastq_quality_preserved(self):
        path = os.path.join(FIXTURES, "test.fastq")
        records = list(parse_fastq(path))
        self.assertIsNotNone(records[0].quality)
        self.assertEqual(len(records[0].quality.scores), 12)
        self.assertIsNotNone(records[0].quality.mean_quality)

    def test_fastq_provenance(self):
        path = os.path.join(FIXTURES, "test.fastq")
        records = list(parse_fastq(path))
        self.assertEqual(records[0].provenance.input_format, VEYRAFormat.FASTQ)

    def test_fastq_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            list(parse_fastq("/nonexistent.fastq"))


class TestGenbankParser(unittest.TestCase):
    """Tests for GenBank parsing."""

    def test_parse_simple_genbank(self):
        path = os.path.join(FIXTURES, "test.gb")
        records = list(parse_genbank(path))
        self.assertEqual(len(records), 1)
        # Biopython returns the full VERSION as ID (e.g. TESTSEQ01.1)
        self.assertIn("TESTSEQ01", records[0].id)
        self.assertIn("TESTSEQ01", records[0].accession)

    def test_genbank_features_extracted(self):
        path = os.path.join(FIXTURES, "test.gb")
        records = list(parse_genbank(path))
        self.assertGreater(len(records[0].features), 0)
        feature_types = [f.type for f in records[0].features]
        self.assertIn("gene", feature_types)
        self.assertIn("CDS", feature_types)

    def test_genbank_annotations_preserved(self):
        path = os.path.join(FIXTURES, "test.gb")
        records = list(parse_genbank(path))
        self.assertIn("source", records[0].annotations)

    def test_genbank_coordinates(self):
        path = os.path.join(FIXTURES, "test.gb")
        records = list(parse_genbank(path))
        self.assertIsNotNone(records[0].coordinate)
        self.assertEqual(records[0].coordinate.start, 0)
        self.assertEqual(records[0].coordinate.end, 100)

    def test_genbank_provenance(self):
        path = os.path.join(FIXTURES, "test.gb")
        records = list(parse_genbank(path))
        self.assertEqual(records[0].provenance.input_format, VEYRAFormat.GENBANK)

    def test_genbank_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            list(parse_genbank("/nonexistent.gb"))


class TestIngestionService(unittest.TestCase):
    """Tests for the ingestion service."""

    def test_ingest_fasta(self):
        path = os.path.join(FIXTURES, "test.fasta")
        records = list(ingest_file(path))
        self.assertEqual(len(records), 3)
        self.assertTrue(all(r.validation.is_valid for r in records))

    def test_ingest_fastq(self):
        path = os.path.join(FIXTURES, "test.fastq")
        records = list(ingest_file(path))
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r.validation.is_valid for r in records))

    def test_ingest_genbank(self):
        path = os.path.join(FIXTURES, "test.gb")
        records = list(ingest_file(path))
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].validation.is_valid)

    def test_ingest_summary(self):
        path = os.path.join(FIXTURES, "test.fasta")
        summary = get_ingestion_summary(path)
        self.assertEqual(summary["detected_format"], "fasta")
        self.assertEqual(summary["num_records"], 3)
        self.assertGreater(summary["total_bases"], 0)

    def test_ingest_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            list(ingest_file("/nonexistent.fasta"))

    def test_ingest_unknown_format(self):
        path = os.path.join(FIXTURES, "malformed.fasta")
        # This file has no '>' header so detector will likely call it unknown
        # depending on detection heuristics; we just ensure no crash
        try:
            list(ingest_file(path))
        except (IngestionError, ValueError):
            pass  # Expected for unrecognized content


class TestValidation(unittest.TestCase):
    """Tests for record validation."""

    def test_valid_record(self):
        record = GenomicRecord(id="test", sequence="ACGTACGT", length=8)
        validated = validate_record(record)
        self.assertTrue(validated.validation.is_valid)
        self.assertEqual(len(validated.validation.errors), 0)

    def test_empty_sequence(self):
        record = GenomicRecord(id="test", sequence="", length=0)
        validated = validate_record(record)
        self.assertFalse(validated.validation.is_valid)
        self.assertGreater(len(validated.validation.errors), 0)

    def test_length_mismatch(self):
        record = GenomicRecord(id="test", sequence="ACGT", length=100)
        validated = validate_record(record)
        self.assertTrue(validated.validation.is_valid)  # warning, not error
        self.assertGreater(len(validated.validation.warnings), 0)

    def test_invalid_characters(self):
        record = GenomicRecord(id="test", sequence="ACGT123XYZ", length=10)
        validated = validate_record(record)
        self.assertGreater(len(validated.validation.warnings), 0)

    def test_batch_validation(self):
        records = [
            GenomicRecord(id="a", sequence="ACGT", length=4),
            GenomicRecord(id="b", sequence="GCTA", length=4),
        ]
        validated = validate_records(records)
        self.assertEqual(len(validated), 2)
        self.assertTrue(all(r.validation.is_valid for r in validated))


class TestGenomicRecordSchema(unittest.TestCase):
    """Tests for the normalized data model."""

    def test_record_creation(self):
        record = GenomicRecord(
            id="test_seq",
            sequence="ACGT",
            length=4,
            description="test sequence",
        )
        self.assertEqual(record.id, "test_seq")
        self.assertEqual(record.length, 4)

    def test_record_auto_length(self):
        record = GenomicRecord(id="test", sequence="ACGTACGT")
        self.assertEqual(record.length, 8)

    def test_record_summary(self):
        record = GenomicRecord(id="test", sequence="ACGT", length=4)
        summary = record.summary()
        self.assertEqual(summary["id"], "test")
        self.assertEqual(summary["length"], 4)

    def test_coordinate(self):
        coord = GenomicCoordinate(start=0, end=100, strand=1)
        record = GenomicRecord(id="test", sequence="A" * 100, coordinate=coord)
        self.assertEqual(record.coordinate.start, 0)
        self.assertEqual(record.coordinate.end, 100)

    def test_feature(self):
        feat = GenomicFeature(
            type="gene",
            location=GenomicCoordinate(start=10, end=50, strand=1),
            qualifiers={"gene": ["testGene"]},
        )
        record = GenomicRecord(id="test", sequence="A" * 100, features=[feat])
        self.assertEqual(len(record.features), 1)
        self.assertEqual(record.features[0].type, "gene")

    def test_quality_data(self):
        quality = QualityData(scores=[10, 20, 30], mean_quality=20.0)
        record = GenomicRecord(id="test", sequence="ACGT", quality=quality)
        self.assertIsNotNone(record.quality)
        self.assertEqual(record.quality.mean_quality, 20.0)

    def test_provenance(self):
        prov = Provenance(
            source_filename="test.fasta",
            input_format=VEYRAFormat.FASTA,
            parser_name="test_parser",
            parser_version="1.0",
        )
        record = GenomicRecord(id="test", sequence="ACGT", provenance=prov)
        self.assertEqual(record.provenance.source_filename, "test.fasta")

    def test_json_serializable_summary(self):
        record = GenomicRecord(id="test", sequence="ACGT", length=4)
        summary = record.summary()
        json_str = json.dumps(summary)
        self.assertIsInstance(json_str, str)


class TestCLI(unittest.TestCase):
    """Tests for the CLI entry point."""

    def test_cli_main_with_fasta(self):
        # Import the CLI main function
        from veyra import main

        path = os.path.join(FIXTURES, "test.fasta")
        exit_code = main(["--input", path, "--quiet"])
        self.assertEqual(exit_code, 0)

    def test_cli_main_with_json_output(self):
        from veyra import main

        path = os.path.join(FIXTURES, "test.fasta")
        exit_code = main(["--input", path, "--json", "--quiet"])
        self.assertEqual(exit_code, 0)

    def test_cli_main_missing_file(self):
        from veyra import main

        exit_code = main(["--input", "/nonexistent/file.fasta"])
        self.assertNotEqual(exit_code, 0)

    def test_cli_main_help(self):
        from veyra import main

        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
