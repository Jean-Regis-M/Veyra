/**
 * Client-side FASTA/FASTQ/GenBank parsing — runs entirely in the browser,
 * no upload. Plain text extraction (record boundaries, headers), not
 * scientific computation; real PAM/GC/CFD scoring still runs through the
 * backend once the extracted sequence reaches it. Kept out of a server
 * route deliberately: routing a multipart file through any Vercel
 * serverless function hits its ~4.5MB request-body cap on larger files,
 * and this operation never needed a server round-trip in the first place.
 */

export interface ParsedFastaRecord {
  id: string;
  sequence: string;
  length: number;
  description: string;
  accession: string | null;
}

function parseFasta(text: string): ParsedFastaRecord[] {
  const blocks = text.split(/^>/m).slice(1);
  return blocks
    .map((block) => {
      const [headerLine, ...rest] = block.split(/\r?\n/);
      const [id, ...descParts] = headerLine.trim().split(/\s+/);
      const fullSeq = rest.join("").replace(/\s+/g, "").toUpperCase();
      const truncatedSeq = fullSeq.length > 25000 ? fullSeq.slice(0, 25000) : fullSeq;
      return {
        id: id ?? "",
        description: descParts.join(" "),
        accession: null,
        sequence: truncatedSeq,
        length: fullSeq.length,
      };
    })
    .filter((r) => r.sequence.length > 0);
}

function parseFastq(text: string): ParsedFastaRecord[] {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  const records: ParsedFastaRecord[] = [];
  for (let i = 0; i + 1 < lines.length; i += 4) {
    if (!lines[i].startsWith("@")) continue;
    const [id, ...descParts] = lines[i].slice(1).trim().split(/\s+/);
    const fullSeq = lines[i + 1].trim().toUpperCase();
    const truncatedSeq = fullSeq.length > 25000 ? fullSeq.slice(0, 25000) : fullSeq;
    records.push({ id, description: descParts.join(" "), accession: null, sequence: truncatedSeq, length: fullSeq.length });
  }
  return records;
}

function parseGenbank(text: string): ParsedFastaRecord[] {
  const records: ParsedFastaRecord[] = [];
  const recordPattern = /^LOCUS\s+(\S+)[\s\S]*?ORIGIN\s*\n([\s\S]*?)\n\/\//gm;
  let match: RegExpExecArray | null;
  while ((match = recordPattern.exec(text)) !== null) {
    const [, id, originBlock] = match;
    const fullSeq = originBlock.replace(/[^a-zA-Z]/g, "").toUpperCase();
    if (fullSeq.length > 0) {
      const truncatedSeq = fullSeq.length > 25000 ? fullSeq.slice(0, 25000) : fullSeq;
      records.push({ id, description: "", accession: id, sequence: truncatedSeq, length: fullSeq.length });
    }
  }
  return records;
}

// Same sniffing rule the backend's own format detector uses (content, not
// extension, is authoritative): a leading '>' is FASTA, a leading '@' with a
// '+' separator on the third line of a 4-line record is FASTQ, and a LOCUS/
// ID/ACCESSION header is GenBank.
function detectFormat(text: string): "fasta" | "fastq" | "genbank" | null {
  const trimmed = text.trimStart();
  if (trimmed.startsWith(">")) return "fasta";
  if (trimmed.startsWith("@")) {
    const lines = trimmed.split(/\r?\n/);
    return lines.length >= 4 && lines[2]?.trim().startsWith("+") ? "fastq" : null;
  }
  if (/^(LOCUS|ID {3}|ACCESSION )/.test(trimmed)) return "genbank";
  return null;
}

export type ParseFileResult =
  | { ok: true; rows: ParsedFastaRecord[]; detectedFormat: "fasta" | "fastq" | "genbank" }
  | { ok: false; error: string };

export async function parseSequenceFile(file: File): Promise<ParseFileResult> {
  const text = await file.text();
  const format = detectFormat(text);
  if (!format) {
    return { ok: false, error: "Could not detect FASTA, FASTQ, or GenBank format from the file's content." };
  }
  const rows = format === "fasta" ? parseFasta(text) : format === "fastq" ? parseFastq(text) : parseGenbank(text);
  if (rows.length === 0) {
    return { ok: false, error: `Detected format "${format}" but no sequence could be extracted.` };
  }
  return { ok: true, rows, detectedFormat: format };
}
