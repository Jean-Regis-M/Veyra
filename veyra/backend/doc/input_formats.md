# Supported Input Formats

## FASTA

- Standard nucleotide FASTA format
- Single or multi-record files
- Extensions: `.fa`, `.fasta`, `.fna`, `.faa`, `.fns`, `.frn`
- Detection: file starts with `>` header line
- Parsing: Biopython `SimpleFastaParser`

### Fields captured
- Record ID (first word after `>`)
- Full description (rest of header line)
- Sequence (uppercased)
- Accession (extracted from ID where possible)

## FASTQ

- Standard Sanger/Illumina FASTQ format
- Phred quality scores preserved
- Extensions: `.fq`, `.fastq`, `.fqr`
- Detection: `@` header followed by `+` quality separator
- Parsing: Biopython `SeqIO.parse` with `fastq` format

### Fields captured
- Read ID
- Sequence (uppercased)
- Quality scores (Phred scale)
- Mean, min, max quality statistics

## GenBank

- GenBank flat file format
- Single or multi-record files
- Extensions: `.gb`, `.gbk`, `.gbff`, `.genbank`
- Detection: file starts with `LOCUS ` line
- Parsing: Biopython `SeqIO.parse` with `genbank` format

### Fields captured
- Locus ID and accession
- Source organism and taxonomy
- All annotated features (gene, CDS, mRNA, etc.) with qualifiers
- Genomic coordinates (start, end, strand)
- Assembly/version information
- All record annotations (source, definition, keywords, etc.)

## Format Detection Strategy

1. **Extension check** – Quick hint from file extension
2. **Content inspection** – Read first 20 lines:
   - `LOCUS ` prefix → GenBank
   - `>` prefix → FASTA
   - `@` prefix with `+` separator → FASTQ
3. **Fallback** – Extension used if content is ambiguous
4. **Unknown** – If neither extension nor content matches → `UNKNOWN`
