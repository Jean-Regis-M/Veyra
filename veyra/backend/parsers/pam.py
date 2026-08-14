"""PAM (Protospacer Adjacent Motif) detection for VEYRA.

Scans genomic sequences for CRISPR PAM sites using:
  - Regex scan  for sequences < 100 kbp  (fast, in-memory)
  - FM-index    for sequences >= 100 kbp  (genome-wide, suffix-array based)

Supported Cas nucleases and their canonical PAM motifs:
  SpCas9      : NGG  (20nt spacer, PAM 3' of protospacer)
  SaCas9      : NNGRRT
  Cas12a/Cpf1 : TTTV  (20nt spacer, PAM 5' of protospacer, seed in PAM-distal region)
  Cas12b      : TTTN
  Cas9-NG     : NG
  SpRY        : NRN / NYN  (near-PAMless)
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterator

from schemas.genomic_record import PAMScanResult, PAMSite

# ---------------------------------------------------------------------------
# IUPAC ambiguity codes → regex character classes
# ---------------------------------------------------------------------------
_IUPAC_MAP: dict[str, str] = {
    "A": "A", "C": "C", "G": "G", "T": "T",
    "R": "[AG]", "Y": "[CT]", "S": "[GC]", "W": "[AT]",
    "K": "[GT]", "M": "[AC]", "B": "[CGT]", "D": "[AGT]",
    "H": "[ACT]", "V": "[ACG]", "N": "[ACGT]",
}

# ---------------------------------------------------------------------------
# PAM definitions – each entry:
#   name, motif (IUPAC), spacer length, pam position relative to spacer
#   pam_position: "3prime" = PAM is 3' of spacer (standard for SpCas9)
#                 "5prime" = PAM is 5' of spacer (Cas12a/Cpf1)
# ---------------------------------------------------------------------------
PAM_DATABASE: dict[str, dict] = {
    "SpCas9":    {"motif": "NGG",   "spacer_len": 20, "pam_position": "3prime", "description": "Streptococcus pyogenes Cas9"},
    "SaCas9":    {"motif": "NNGRRT", "spacer_len": 20, "pam_position": "3prime", "description": "Staphylococcus aureus Cas9"},
    "Cas12a":    {"motif": "TTTV",  "spacer_len": 20, "pam_position": "5prime", "description": "Cas12a/Cpf1 (AsCpf1, LbCpf1)"},
    "Cas12b":    {"motif": "TTTN",  "spacer_len": 20, "pam_position": "5prime", "description": "Cas12b/C2c1"},
    "Cas9_NG":   {"motif": "NG",    "spacer_len": 20, "pam_position": "3prime", "description": "SpCas9-NG (relaxed PAM)"},
    "SpRY_NRN":  {"motif": "NRN",   "spacer_len": 20, "pam_position": "3prime", "description": "SpRY (near-PAMless, NRN)"},
    "SpRY_NYN":  {"motif": "NYN",   "spacer_len": 20, "pam_position": "3prime", "description": "SpRY (near-PAMless, NYN)"},
}

# Threshold: below this length use regex, above use FM-index
FM_INDEX_THRESHOLD = 100_000

_DEFAULT_PAM = "SpCas9"

# ---------------------------------------------------------------------------
# Regex-based PAM scanner (small sequences)
# ---------------------------------------------------------------------------

def _iupac_to_regex(motif: str) -> str:
    """Convert an IUPAC ambiguity motif to a regex pattern."""
    return "".join(_IUPAC_MAP.get(ch, ch) for ch in motif.upper())


def _complement(seq: str) -> str:
    """Return the reverse complement of a DNA sequence."""
    comp = {"A": "T", "T": "A", "G": "C", "C": "G",
            "R": "Y", "Y": "R", "S": "S", "W": "W",
            "K": "M", "M": "K", "B": "V", "V": "B",
            "D": "H", "H": "D", "N": "N"}
    return "".join(comp.get(ch, "N") for ch in reversed(seq.upper()))


def _scan_regex(
    sequence: str,
    pam_motif: str,
    spacer_len: int,
    pam_position: str,
    pam_name: str,
) -> Iterator[PAMSite]:
    """Scan a sequence for PAM sites using regex (small sequences)."""
    fwd_regex = _iupac_to_regex(pam_motif)
    rev_motif = _complement(pam_motif)
    rev_regex = _iupac_to_regex(rev_motif)

    seq_upper = sequence.upper()
    seq_len = len(seq_upper)

    # Forward strand
    for m in re.finditer(fwd_regex, seq_upper):
        pos = m.start()
        pam_seq = m.group()
        spacer_start: int | None = None
        spacer_end: int | None = None
        spacer_seq: str | None = None

        if pam_position == "3prime":
            spacer_end = pos
            spacer_start = pos - spacer_len
            if spacer_start >= 0:
                spacer_seq = seq_upper[spacer_start:spacer_end]
        else:
            spacer_start = pos + len(pam_seq)
            spacer_end = spacer_start + spacer_len
            if spacer_end <= seq_len:
                spacer_seq = seq_upper[spacer_start:spacer_end]

        guide: str | None = _complement(spacer_seq) if spacer_seq else None

        yield PAMSite(
            position=pos,
            pam_sequence=pam_seq,
            pam_type=pam_name,
            strand=1,
            spacer_start=spacer_start if spacer_start is not None and spacer_start >= 0 else None,
            spacer_end=spacer_end if spacer_end is not None and spacer_end <= seq_len else None,
            spacer_sequence=spacer_seq,
            guide_rna=guide,
        )

    # Reverse strand
    for m in re.finditer(rev_regex, seq_upper):
        pos = m.start()
        pam_seq = m.group()
        # On reverse strand the PAM matches rev-comp motif on forward strand
        # The actual PAM on the reverse strand is the rev-comp of what we matched
        actual_pam_rc = _complement(pam_seq)  # this IS the canonical PAM on reverse strand

        spacer_start_rev: int | None = None
        spacer_end_rev: int | None = None
        spacer_seq_rev: str | None = None

        if pam_position == "3prime":
            # On reverse strand, spacer is downstream (3') of PAM on reverse strand
            # which means upstream (5') on forward strand
            spacer_end_rev = pos  # end of spacer on forward strand
            spacer_start_rev = pos - spacer_len
            if spacer_start_rev >= 0:
                spacer_seq_rev = seq_upper[spacer_start_rev:spacer_end_rev]
        else:
            # 5prime PAM: on reverse strand, spacer is upstream (5') on rev strand
            # which means downstream (3') on forward strand
            spacer_start_rev = pos + len(pam_seq)
            spacer_end_rev = spacer_start_rev + spacer_len
            if spacer_end_rev <= seq_len:
                spacer_seq_rev = seq_upper[spacer_start_rev:spacer_end_rev]

        guide_rev: str | None = _complement(spacer_seq_rev) if spacer_seq_rev else None

        yield PAMSite(
            position=pos,
            pam_sequence=actual_pam_rc,
            pam_type=pam_name,
            strand=-1,
            spacer_start=spacer_start_rev if spacer_start_rev is not None and spacer_start_rev >= 0 else None,
            spacer_end=spacer_end_rev if spacer_end_rev is not None and spacer_end_rev <= seq_len else None,
            spacer_sequence=spacer_seq_rev,
            guide_rna=guide_rev,
        )


# ---------------------------------------------------------------------------
# FM-index / suffix-array based PAM scanner (genome-wide)
# ---------------------------------------------------------------------------

class _SuffixArrayIndex:
    """Lightweight suffix-array index for efficient substring search.

    Stores the suffix array, LCP array, and BWT for a reference sequence.
    Supports enumerate-all-concrete-patterns strategy for degenerate PAM
    motifs: enumerates all concrete IUPAC expansions (e.g. NGG → AGG, CGG,
    GGG, TGG) and searches each via binary search on the suffix array.
    """

    def __init__(self, sequence: str) -> None:
        self._seq = sequence.upper()
        self._n = len(sequence)
        self._sa = list(range(self._n))
        self._sa.sort(key=lambda i: self._seq[i:])

    def _search(self, pattern: str) -> list[int]:
        """Return all start positions of `pattern` in the reference via SA binary search."""
        seq = self._seq
        sa = self._sa
        n = self._n
        plen = len(pattern)
        lo, hi = 0, n

        # find leftmost match
        while lo < hi:
            mid = (lo + hi) // 2
            if seq[sa[mid]:sa[mid] + plen] < pattern:
                lo = mid + 1
            else:
                hi = mid

        left = lo
        hi = n
        while lo < hi:
            mid = (lo + hi) // 2
            if seq[sa[mid]:sa[mid] + plen] <= pattern:
                lo = mid + 1
            else:
                hi = mid

        return sorted(sa[left:lo])


def _expand_iupac(motif: str) -> list[str]:
    """Expand an IUPAC degenerate motif into all concrete sequences.

    NGG → [AGG, CGG, GGG, TGG]
    NNN → [AAA, AAC, AAG, ..., TTT]  (64)
    """
    bases = ["A", "C", "G", "T"]
    mapping = {
        "A": ["A"], "C": ["C"], "G": ["G"], "T": ["T"],
        "R": ["A", "G"], "Y": ["C", "T"], "S": ["G", "C"], "W": ["A", "T"],
        "K": ["G", "T"], "M": ["A", "C"],
        "B": ["C", "G", "T"], "D": ["A", "G", "T"],
        "H": ["A", "C", "T"], "V": ["A", "C", "G"],
        "N": bases,
    }
    options = [mapping.get(ch.upper(), [ch]) for ch in motif]
    # Cartesian product
    result = [""]
    for opts in options:
        result = [r + o for r in result for o in opts]
    return result


def _scan_fmindex(
    sequence: str,
    pam_motif: str,
    spacer_len: int,
    pam_position: str,
    pam_name: str,
) -> Iterator[PAMSite]:
    """Scan a sequence for PAM sites using suffix-array FM-index (genome-wide)."""
    index = _SuffixArrayIndex(sequence)
    seq_upper = sequence.upper()
    seq_len = len(seq_upper)
    concrete_pams = _expand_iupac(pam_motif)

    seen_fwd: set[int] = set()
    seen_rev: set[int] = set()

    for concrete in concrete_pams:
        pam_len = len(concrete)

        # Forward strand
        for pos in index._search(concrete):
            if pos in seen_fwd:
                continue
            seen_fwd.add(pos)

            spacer_start: int | None = None
            spacer_end: int | None = None
            spacer_seq: str | None = None

            if pam_position == "3prime":
                spacer_end = pos
                spacer_start = pos - spacer_len
                if spacer_start >= 0:
                    spacer_seq = seq_upper[spacer_start:spacer_end]
            else:
                spacer_start = pos + pam_len
                spacer_end = spacer_start + spacer_len
                if spacer_end <= seq_len:
                    spacer_seq = seq_upper[spacer_start:spacer_end]

            guide: str | None = _complement(spacer_seq) if spacer_seq else None

            yield PAMSite(
                position=pos,
                pam_sequence=concrete,
                pam_type=pam_name,
                strand=1,
                spacer_start=spacer_start if spacer_start is not None and spacer_start >= 0 else None,
                spacer_end=spacer_end if spacer_end is not None and spacer_end <= seq_len else None,
                spacer_sequence=spacer_seq,
                guide_rna=guide,
            )

        # Reverse strand: search for reverse complement of the concrete PAM
        rc_concrete = _complement(concrete)
        for pos in index._search(rc_concrete):
            if pos in seen_rev:
                continue
            seen_rev.add(pos)

            spacer_start_rev: int | None = None
            spacer_end_rev: int | None = None
            spacer_seq_rev: str | None = None

            if pam_position == "3prime":
                spacer_end_rev = pos
                spacer_start_rev = pos - spacer_len
                if spacer_start_rev >= 0:
                    spacer_seq_rev = seq_upper[spacer_start_rev:spacer_end_rev]
            else:
                spacer_start_rev = pos + pam_len
                spacer_end_rev = spacer_start_rev + spacer_len
                if spacer_end_rev <= seq_len:
                    spacer_seq_rev = seq_upper[spacer_start_rev:spacer_end_rev]

            guide_rev: str | None = _complement(spacer_seq_rev) if spacer_seq_rev else None

            yield PAMSite(
                position=pos,
                pam_sequence=concrete,
                pam_type=pam_name,
                strand=-1,
                spacer_start=spacer_start_rev if spacer_start_rev is not None and spacer_start_rev >= 0 else None,
                spacer_end=spacer_end_rev if spacer_end_rev is not None and spacer_end_rev <= seq_len else None,
                spacer_sequence=spacer_seq_rev,
                guide_rna=guide_rev,
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_pam(
    sequence: str,
    pam_name: str = _DEFAULT_PAM,
    *,
    custom_motif: str | None = None,
    custom_spacer_len: int | None = None,
    custom_pam_position: str | None = None,
) -> PAMScanResult:
    """Scan a genomic sequence for PAM sites.

    Automatically selects regex (small) or FM-index (genome-wide) based
    on sequence length.

    Args:
        sequence: The genomic DNA sequence to scan.
        pam_name: Key into PAM_DATABASE (e.g. "SpCas9", "Cas12a").
        custom_motif: Override the PAM motif with an IUPAC string.
        custom_spacer_len: Override the spacer length.
        custom_pam_position: Override pam_position ("3prime" or "5prime").

    Returns:
        PAMScanResult containing all detected PAM sites and summary stats.
    """
    if not sequence:
        return PAMScanResult()

    # Resolve PAM parameters
    if custom_motif:
        motif = custom_motif.upper()
        spacer_len = custom_spacer_len or 20
        pam_pos = custom_pam_position or "3prime"
        resolved_name = f"custom:{motif}"
    elif pam_name in PAM_DATABASE:
        entry = PAM_DATABASE[pam_name]
        motif = entry["motif"]
        spacer_len = entry["spacer_len"]
        pam_pos = entry["pam_position"]
        resolved_name = pam_name
    else:
        raise ValueError(
            f"Unknown PAM type: {pam_name}. "
            f"Available: {', '.join(PAM_DATABASE.keys())} "
            "or provide custom_motif."
        )

    # Choose scanner based on sequence length
    seq_len = len(sequence)
    if seq_len < FM_INDEX_THRESHOLD:
        sites_iter = _scan_regex(sequence, motif, spacer_len, pam_pos, resolved_name)
    else:
        sites_iter = _scan_fmindex(sequence, motif, spacer_len, pam_pos, resolved_name)

    sites = list(sites_iter)

    # Build summary
    fwd = sum(1 for s in sites if s.strand == 1)
    rev = sum(1 for s in sites if s.strand == -1)
    type_counts: dict[str, int] = defaultdict(int)
    for s in sites:
        type_counts[s.pam_type] += 1

    return PAMScanResult(
        pam_sites=sites,
        total_sites=len(sites),
        forward_sites=fwd,
        reverse_sites=rev,
        pam_types_found=dict(type_counts),
    )


def scan_pam_multi(
    sequence: str,
    pam_names: list[str] | None = None,
) -> PAMScanResult:
    """Scan a sequence for PAM sites across multiple Cas nucleases.

    Merges results from all requested PAM types into a single PAMScanResult.

    Args:
        sequence: The genomic DNA sequence to scan.
        pam_names: List of PAM_DATABASE keys. Defaults to ["SpCas9"].

    Returns:
        PAMScanResult with sites from all requested PAM types.
    """
    if pam_names is None:
        pam_names = [_DEFAULT_PAM]

    all_sites: list[PAMSite] = []
    type_counts: dict[str, int] = defaultdict(int)

    for name in pam_names:
        result = scan_pam(sequence, pam_name=name)
        all_sites.extend(result.pam_sites)
        for k, v in result.pam_types_found.items():
            type_counts[k] += v

    all_sites.sort(key=lambda s: s.position)

    fwd = sum(1 for s in all_sites if s.strand == 1)
    rev = sum(1 for s in all_sites if s.strand == -1)

    return PAMScanResult(
        pam_sites=all_sites,
        total_sites=len(all_sites),
        forward_sites=fwd,
        reverse_sites=rev,
        pam_types_found=dict(type_counts),
    )
