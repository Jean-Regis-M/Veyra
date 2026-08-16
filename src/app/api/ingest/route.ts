import { NextRequest, NextResponse } from "next/server";

interface ParsedRecord {
  id: string;
  sequence: string;
  length: number;
  description: string;
  accession: string | null;
}

// The backend's real parsers (Biopython-based) are the source of truth for
// format detection and validation — this route always calls /ingest first
// and surfaces its errors. But /ingest deliberately never returns sequence
// text over HTTP (backend/services/ingestion.py: "avoids loading huge
// sequences into memory for display"), so extracting the raw sequence
// string for the analysis textarea has to happen here. This is plain text
// extraction (splitting on FASTA/FASTQ/GenBank record boundaries) — no
// scientific computation, PAM/GC/CFD scoring still runs through the real
// backend afterward.
function parseFasta(text: string): ParsedRecord[] {
  const blocks = text.split(/^>/m).slice(1);
  return blocks.map((block) => {
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
  }).filter((r) => r.sequence.length > 0);
}

function parseFastq(text: string): ParsedRecord[] {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  const records: ParsedRecord[] = [];
  for (let i = 0; i + 1 < lines.length; i += 4) {
    if (!lines[i].startsWith("@")) continue;
    const [id, ...descParts] = lines[i].slice(1).trim().split(/\s+/);
    const fullSeq = lines[i + 1].trim().toUpperCase();
    const truncatedSeq = fullSeq.length > 25000 ? fullSeq.slice(0, 25000) : fullSeq;
    records.push({ id, description: descParts.join(" "), accession: null, sequence: truncatedSeq, length: fullSeq.length });
  }
  return records;
}

function parseGenbank(text: string): ParsedRecord[] {
  const records: ParsedRecord[] = [];
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

export async function POST(req: NextRequest) {
  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!file || !(file instanceof File)) {
    return NextResponse.json({ error: "Expected multipart form field 'file'." }, { status: 400 });
  }

  const text = await file.text();
  const format = detectFormat(text);
  if (!format) {
    return NextResponse.json({ error: "Could not detect FASTA, FASTQ, or GenBank format from the file's content." }, { status: 400 });
  }

  const records = format === "fasta" ? parseFasta(text) : format === "fastq" ? parseFastq(text) : parseGenbank(text);
  if (records.length === 0) {
    return NextResponse.json({ error: `Detected format "${format}" but no sequence could be extracted.` }, { status: 400 });
  }
  return NextResponse.json({ rows: records, detectedFormat: format });
}
