export interface ExampleSequence {
  id: string;
  label: string;
  sequence: string;
}

// Short synthetic sequences chosen to reliably surface at least one PAM site,
// a range of GC content, and a couple of near-duplicate off-target windows —
// useful for demoing the pipeline end-to-end, not real clinical loci.
export const EXAMPLE_SEQUENCES: ExampleSequence[] = [
  {
    id: "demo-1",
    label: "Balanced GC, single locus",
    sequence:
      "ACGTGACCTGAGGCTGATCCGTAGGCTAGCTAGGCTTACGGAGGCTAGCTAGGCATCGATCGATCGGAGGCTAGCATCGATGCTAGCATGGAGGCTAGCTAGCTAGCATGCATGCTAGCTAGGAGGCTAGCATGCTAGCTAGCATCGATCG",
  },
  {
    id: "demo-2",
    label: "High GC, repetitive off-targets",
    sequence:
      "GCGCGCGGAGGCGCGCGCTGGAGGCGCGCGCTAGGAGGCGCGCGATGGAGGCGCGCGCTGGCGGAGGCGCGCGATAGGAGGCGCGCGCTCGGAGGCGCGCGATGGAGGCGCGCGCTAGGAGG",
  },
];
