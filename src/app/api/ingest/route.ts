import { NextRequest, NextResponse } from "next/server";
import { mkdtemp, writeFile, rm } from "fs/promises";
import { tmpdir } from "os";
import path from "path";
import { BACKEND_BASE_URL } from "@/lib/backend";

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
    return {
      id: id ?? "",
      description: descParts.join(" "),
      accession: null,
      sequence: rest.join("").replace(/\s+/g, "").toUpperCase(),
      length: 0,
    };
  }).map((r) => ({ ...r, length: r.sequence.length })).filter((r) => r.sequence.length > 0);
}

function parseFastq(text: string): ParsedRecord[] {
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  const records: ParsedRecord[] = [];
  for (let i = 0; i + 1 < lines.length; i += 4) {
    if (!lines[i].startsWith("@")) continue;
    const [id, ...descParts] = lines[i].slice(1).trim().split(/\s+/);
    const sequence = lines[i + 1].trim().toUpperCase();
    records.push({ id, description: descParts.join(" "), accession: null, sequence, length: sequence.length });
  }
  return records;
}

function parseGenbank(text: string): ParsedRecord[] {
  const records: ParsedRecord[] = [];
  const recordPattern = /^LOCUS\s+(\S+)[\s\S]*?ORIGIN\s*\n([\s\S]*?)\n\/\//gm;
  let match: RegExpExecArray | null;
  while ((match = recordPattern.exec(text)) !== null) {
    const [, id, originBlock] = match;
    const sequence = originBlock.replace(/[^a-zA-Z]/g, "").toUpperCase();
    if (sequence.length > 0) {
      records.push({ id, description: "", accession: id, sequence, length: sequence.length });
    }
  }
  return records;
}

export async function POST(req: NextRequest) {
  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!file || !(file instanceof File)) {
    return NextResponse.json({ error: "Expected multipart form field 'file'." }, { status: 400 });
  }

  const ext = path.extname(file.name) || ".fasta";
  const dir = await mkdtemp(path.join(tmpdir(), "veyra-ingest-"));
  const filePath = path.join(dir, `upload${ext}`);

  try {
    const bytes = Buffer.from(await file.arrayBuffer());
    const text = bytes.toString("utf-8");
    await writeFile(filePath, bytes);

    const res = await fetch(`${BACKEND_BASE_URL}/ingest`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ input_path: filePath, pam_scan: false }),
    });
    const json = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = json?.detail?.errors?.join("; ") ?? json?.detail ?? `Backend returned HTTP ${res.status}`;
      return NextResponse.json({ error: String(detail) }, { status: 400 });
    }

    const format = json?.summary?.detected_format as string | undefined;
    const records =
      format === "fasta" ? parseFasta(text) : format === "fastq" ? parseFastq(text) : format === "genbank" ? parseGenbank(text) : [];

    if (records.length === 0) {
      return NextResponse.json({ error: `Backend confirmed format "${format}" but no sequence could be extracted.` }, { status: 400 });
    }
    return NextResponse.json({ rows: records, detectedFormat: format });
  } catch {
    return NextResponse.json({ error: "VEYRA backend unreachable — start it and retry." }, { status: 502 });
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
