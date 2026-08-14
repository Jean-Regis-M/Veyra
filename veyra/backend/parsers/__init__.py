"""VEYRA parsers package.

Provides format-specific parsers and a format detector.
"""

from parsers.detector import detect_format, FormatDetectionError
from parsers.fasta_parser import parse as parse_fasta
from parsers.fastq_parser import parse as parse_fastq
from parsers.genbank_parser import parse as parse_genbank

__all__ = [
    "detect_format",
    "FormatDetectionError",
    "parse_fasta",
    "parse_fastq",
    "parse_genbank",
]
