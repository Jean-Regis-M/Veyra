# Melting Temperature Calculation

## Purpose

`compute_melting_temp` is a deterministic sequence-analysis tool that estimates duplex melting temperature (Tm) for DNA sequences.

**This tool produces estimated physicochemical properties.** It does NOT predict CRISPR cleavage efficiency or specificity.

## Methods

Uses Biopython's `MeltingTemp` module for established implementations:

### Nearest-Neighbor (default)

```python
from Bio.SeqUtils.MeltingTemp import Tm_NN
tm = Tm_NN(seq, Na=na_conc, Mg=mg_conc, dnac1=primer_conc/2, dnac2=primer_conc/2, saltcorr=5)
```

- Uses SantaLucia 1998 salt correction (saltcorr=5)
- Accounts for Na+, Mg2+, and primer concentration
- Most accurate method for short oligonucleotides

### Wallace

```python
from Bio.SeqUtils.MeltingTemp import Tm_Wallace
tm = Tm_Wallace(seq)
```

- Formula: `Tm = 2*(A+T) + 4*(G+C)`
- Does NOT use salt or concentration parameters
- Simple approximation for quick estimates

### GC-Percent

```python
from Bio.SeqUtils.MeltingTemp import Tm_GC
tm = Tm_GC(seq, Na=na_conc, Mg=mg_conc, saltcorr=0)
```

- Salt-dependent GC-based approximation
- Less accurate than nearest-neighbor

## Parameters

| Parameter | Type | Default | Valid values/range | Description |
|-----------|------|---------|-------------------|-------------|
| `sequence` | string | required | Standard ACGT | DNA sequence to analyze |
| `tm_method` | string | "nearest_neighbor" | nearest_neighbor, wallace, gc_percent | Tm calculation method |
| `na_conc` | float | 50.0 | >= 0 | Na+ concentration (mM) |
| `mg_conc` | float | 0.0 | >= 0 | Mg2+ concentration (mM) |
| `primer_conc` | float | 250.0 | > 0 | Primer concentration (nM) |
| `seed_region_length` | int | 10 | > 0, <= seq_len | Seed region length for seed Tm |
| `compute_seed_tm` | bool | false | true/false | Compute Tm for 3' seed region |
| `round_decimals` | int | 2 | >= 0 | Decimal places for rounding |

## Seed Tm

When `compute_seed_tm = true`, computes Tm for the 3' end of the sequence:

```python
seed_seq = bio_seq[-seed_region_length:]
```

For SpCas9, the seed region is typically the 10-12 nt proximal to the PAM. The implementation uses the 3' end of the provided orientation.

## Rounding

Calculations use full available precision. Rounding is applied only to returned values, not intermediate calculations.

## Output Schema

```json
{
  "tool": "compute_melting_temp",
  "rows": [...],
  "summary": {
    "sequence_length": 20,
    "tm_celsius": 79.21,
    "seed_tm_celsius": null
  },
  "metadata": {
    "tm_method": "nearest_neighbor",
    "na_conc": 50.0,
    "mg_conc": 0.0,
    "primer_conc": 250.0,
    "seed_region_length": null,
    "compute_seed_tm": false,
    "round_decimals": 2,
    "scoring_note": "Melting temperature is an estimated physicochemical property..."
  }
}
```

## Usage

### CLI

```bash
python -m cli.main sequence tm --sequence GCGCGCGCGCGCGCGCGCGC
python -m cli.main sequence tm --sequence GCGCGCGCGCGCGCGCGCGC --tm-method wallace
python -m cli.main sequence tm --sequence GCGCGCGCGCGCGCGCGCGC --compute-seed-tm --seed-region-length 10
```

### Python API

```python
from api import compute_melting_temp

result = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC")
print(result.summary["tm_celsius"])  # 79.21
```

### HTTP API

```bash
curl -X POST http://localhost:8000/sequence/tm \
    -H "Content-Type: application/json" \
    -d '{"sequence": "GCGCGCGCGCGCGCGCGCGC"}'
```

### MCP

```python
from mcp.tools.compute_melting_temp import compute_melting_temp

result = compute_melting_temp("GCGCGCGCGCGCGCGCGCGC")
```

## Computational Cost

Moderate — nearest-neighbor method involves thermodynamic calculations. Suitable for agent workflows but more expensive than GC content or homopolymer detection.

## Limitations

- Wallace method does not use salt or concentration parameters
- Nearest-neighbor method requires standard ACGT bases (no IUPAC ambiguity)
- Tm is an estimate; actual melting behavior depends on experimental conditions
- Not a validated prediction of Cas9 cleavage efficiency or specificity
