"use client";

import React, { useMemo, useState } from "react";
import { Check, Copy, ChevronDown, ChevronRight, ExternalLink } from "lucide-react";

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

interface TableData {
  headers: string[];
  alignments: ("left" | "center" | "right")[];
  rows: string[][];
}

function parseMarkdownTable(lines: string[]): TableData | null {
  if (lines.length < 2) return null;
  const headerLine = lines[0].trim();
  const delimiterLine = lines[1].trim();

  if (!headerLine.includes("|") || !delimiterLine.includes("|")) return null;

  const parseCells = (line: string) =>
    line
      .replace(/^\|/, "")
      .replace(/\|$/, "")
      .split("|")
      .map((c) => c.trim());

  const headers = parseCells(headerLine);
  const delimiters = parseCells(delimiterLine);

  if (headers.length === 0 || headers.length !== delimiters.length) return null;

  const alignments = delimiters.map((d) => {
    const left = d.startsWith(":");
    const right = d.endsWith(":");
    if (left && right) return "center" as const;
    if (right) return "right" as const;
    return "left" as const;
  });

  const rows: string[][] = [];
  for (let i = 2; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line.includes("|")) continue;
    const cells = parseCells(line);
    while (cells.length < headers.length) cells.push("");
    rows.push(cells.slice(0, headers.length));
  }

  return { headers, alignments, rows };
}

function renderInline(text: string): React.ReactNode[] {
  // Tokenize bold, italic, inline code, links, strikethrough
  const nodes: React.ReactNode[] = [];
  let remaining = text;
  let keyIdx = 0;

  while (remaining.length > 0) {
    // 1. Inline Code `code`
    const codeMatch = remaining.match(/^`([^`]+)`/);
    if (codeMatch) {
      nodes.push(
        <code
          key={keyIdx++}
          className="rounded-sm bg-white/10 px-1.5 py-0.5 font-mono text-[11px] text-ai font-medium border border-border/40"
        >
          {codeMatch[1]}
        </code>
      );
      remaining = remaining.slice(codeMatch[0].length);
      continue;
    }

    // 2. Links [text](url)
    const linkMatch = remaining.match(/^\[([^\]]+)\]\(([^)]+)\)/);
    if (linkMatch) {
      const isExternal = linkMatch[2].startsWith("http") || linkMatch[2].startsWith("//");
      nodes.push(
        <a
          key={keyIdx++}
          href={linkMatch[2]}
          target={isExternal ? "_blank" : undefined}
          rel={isExternal ? "noopener noreferrer" : undefined}
          className="text-primary hover:underline font-medium inline-flex items-center gap-0.5"
        >
          {linkMatch[1]}
          {isExternal && <ExternalLink size={10} className="inline opacity-70" />}
        </a>
      );
      remaining = remaining.slice(linkMatch[0].length);
      continue;
    }

    // 3. Bold **text** or __text__
    const boldMatch = remaining.match(/^(\*\*|__)(.*?)\1/);
    if (boldMatch) {
      nodes.push(
        <strong key={keyIdx++} className="font-semibold text-foreground">
          {renderInline(boldMatch[2])}
        </strong>
      );
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }

    // 4. Strikethrough ~~text~~
    const strikeMatch = remaining.match(/^~~(.*?)~~/);
    if (strikeMatch) {
      nodes.push(
        <del key={keyIdx++} className="line-through text-muted/70">
          {renderInline(strikeMatch[1])}
        </del>
      );
      remaining = remaining.slice(strikeMatch[0].length);
      continue;
    }

    // 5. Italic *text* or _text_
    const italicMatch = remaining.match(/^(\*|_)(.*?)\1/);
    if (italicMatch && italicMatch[2].trim().length > 0) {
      nodes.push(
        <em key={keyIdx++} className="italic text-foreground/90">
          {renderInline(italicMatch[2])}
        </em>
      );
      remaining = remaining.slice(italicMatch[0].length);
      continue;
    }

    // Regular plain text chunk up to next special char
    const nextSpecial = remaining.search(/[`\[\*_~]/);
    if (nextSpecial === -1) {
      nodes.push(remaining);
      break;
    } else if (nextSpecial > 0) {
      nodes.push(remaining.slice(0, nextSpecial));
      remaining = remaining.slice(nextSpecial);
    } else {
      // Fallback single character
      nodes.push(remaining[0]);
      remaining = remaining.slice(1);
    }
  }

  return nodes;
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);

  function copyCode() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="my-3 rounded-lg border border-border bg-black/60 overflow-hidden font-mono text-xs">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border/40 bg-white/[0.03] text-muted text-[10px] uppercase tracking-wider">
        <span>{language || "code"}</span>
        <button
          type="button"
          onClick={copyCode}
          className="inline-flex items-center gap-1 hover:text-foreground transition-colors cursor-pointer"
        >
          {copied ? (
            <>
              <Check size={12} className="text-engine" />
              <span className="text-engine">Copied</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3 overflow-x-auto text-foreground/90 whitespace-pre leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function CollapsibleSection({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="my-2 rounded-lg border border-border/60 bg-black/30 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between p-3 text-left font-medium text-xs text-foreground hover:bg-white/5 transition-colors"
      >
        <span>{title}</span>
        {open ? <ChevronDown size={14} className="text-muted" /> : <ChevronRight size={14} className="text-muted" />}
      </button>
      {open && <div className="p-3 border-t border-border/40 text-xs text-muted/90 space-y-2">{children}</div>}
    </div>
  );
}

export function MarkdownViewer({ content, className = "" }: MarkdownViewerProps) {
  const elements = useMemo(() => {
    const rawLines = content.split(/\r?\n/);
    const parsedNodes: React.ReactNode[] = [];
    let i = 0;
    let nodeKey = 0;

    while (i < rawLines.length) {
      const line = rawLines[i];
      const trimmed = line.trim();

      // Empty line
      if (trimmed === "") {
        i++;
        continue;
      }

      // 1. Code Block ```
      if (trimmed.startsWith("```")) {
        const language = trimmed.slice(3).trim();
        const codeLines: string[] = [];
        i++;
        while (i < rawLines.length && !rawLines[i].trim().startsWith("```")) {
          codeLines.push(rawLines[i]);
          i++;
        }
        if (i < rawLines.length) i++; // consume closing ```
        parsedNodes.push(
          <CodeBlock key={nodeKey++} code={codeLines.join("\n")} language={language} />
        );
        continue;
      }

      // 2. Table (| header |)
      if (trimmed.startsWith("|") || (trimmed.includes("|") && rawLines[i + 1]?.trim().includes("|") && rawLines[i + 1]?.trim().includes("-"))) {
        const tableLines: string[] = [];
        while (i < rawLines.length && rawLines[i].trim().includes("|")) {
          tableLines.push(rawLines[i]);
          i++;
        }
        const table = parseMarkdownTable(tableLines);
        if (table) {
          parsedNodes.push(
            <div key={nodeKey++} className="my-4 overflow-x-auto rounded-lg border border-border bg-black/40">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border bg-white/[0.04]">
                    {table.headers.map((h, colIdx) => (
                      <th
                        key={colIdx}
                        className="px-3.5 py-2.5 font-semibold text-foreground tracking-wide text-[11px]"
                        style={{ textAlign: table.alignments[colIdx] }}
                      >
                        {renderInline(h)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {table.rows.map((row, rowIdx) => (
                    <tr key={rowIdx} className="hover:bg-white/[0.02] transition-colors">
                      {row.map((cell, cellIdx) => (
                        <td
                          key={cellIdx}
                          className="px-3.5 py-2 text-foreground/80 text-[11px] veyra-readout"
                          style={{ textAlign: table.alignments[cellIdx] }}
                        >
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
          continue;
        }
      }

      // 3. Headings (# -> ######)
      const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
      if (headingMatch) {
        const level = headingMatch[1].length;
        const text = headingMatch[2].trim();
        const id = text.toLowerCase().replace(/[^\w]+/g, "-");

        const headingClasses: Record<number, string> = {
          1: "text-2xl sm:text-3xl font-display font-semibold text-foreground mt-6 mb-3 border-b border-border/40 pb-2",
          2: "text-xl sm:text-2xl font-display font-semibold text-foreground mt-5 mb-2.5",
          3: "text-lg font-display font-medium text-foreground mt-4 mb-2 text-primary",
          4: "text-base font-semibold text-foreground mt-3 mb-1.5",
          5: "text-sm font-semibold text-foreground mt-3 mb-1",
          6: "text-xs font-semibold text-muted uppercase tracking-wider mt-2 mb-1",
        };

        const Tag = `h${level}` as "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
        parsedNodes.push(
          <Tag key={nodeKey++} id={id} className={headingClasses[level]}>
            {renderInline(text)}
          </Tag>
        );
        i++;
        continue;
      }

      // 4. Horizontal Rule (--- or ***)
      if (trimmed === "---" || trimmed === "***" || trimmed === "___") {
        parsedNodes.push(<hr key={nodeKey++} className="my-6 border-border/40" />);
        i++;
        continue;
      }

      // 5. Blockquote (> text)
      if (trimmed.startsWith(">")) {
        const quoteLines: string[] = [];
        while (i < rawLines.length && rawLines[i].trim().startsWith(">")) {
          quoteLines.push(rawLines[i].trim().replace(/^>\s?/, ""));
          i++;
        }
        parsedNodes.push(
          <blockquote
            key={nodeKey++}
            className="my-3 border-l-2 border-primary/70 bg-primary/5 px-4 py-2 text-xs text-foreground/90 italic rounded-r-md"
          >
            {renderInline(quoteLines.join(" "))}
          </blockquote>
        );
        continue;
      }

      // 6. Unordered List (- or * or +)
      if (/^[-*+]\s+/.test(trimmed)) {
        const items: string[] = [];
        while (i < rawLines.length && /^[-*+]\s+/.test(rawLines[i].trim())) {
          items.push(rawLines[i].trim().replace(/^[-*+]\s+/, ""));
          i++;
        }
        parsedNodes.push(
          <ul key={nodeKey++} className="my-2.5 list-disc list-outside ml-5 space-y-1 text-xs text-foreground/80 leading-relaxed">
            {items.map((item, itemIdx) => (
              <li key={itemIdx}>{renderInline(item)}</li>
            ))}
          </ul>
        );
        continue;
      }

      // 7. Ordered List (1. 2. 3.)
      if (/^\d+\.\s+/.test(trimmed)) {
        const items: string[] = [];
        while (i < rawLines.length && /^\d+\.\s+/.test(rawLines[i].trim())) {
          items.push(rawLines[i].trim().replace(/^\d+\.\s+/, ""));
          i++;
        }
        parsedNodes.push(
          <ol key={nodeKey++} className="my-2.5 list-decimal list-outside ml-5 space-y-1 text-xs text-foreground/80 leading-relaxed">
            {items.map((item, itemIdx) => (
              <li key={itemIdx}>{renderInline(item)}</li>
            ))}
          </ol>
        );
        continue;
      }

      // 8. Collapsible section :::details Title ... :::
      if (trimmed.startsWith(":::details")) {
        const title = trimmed.replace(/^:::details\s*/, "") || "Details";
        const innerLines: string[] = [];
        i++;
        while (i < rawLines.length && !rawLines[i].trim().startsWith(":::")) {
          innerLines.push(rawLines[i]);
          i++;
        }
        if (i < rawLines.length) i++; // consume closing :::
        parsedNodes.push(
          <CollapsibleSection key={nodeKey++} title={title}>
            <MarkdownViewer content={innerLines.join("\n")} />
          </CollapsibleSection>
        );
        continue;
      }

      // 9. Standard Paragraph
      parsedNodes.push(
        <p key={nodeKey++} className="my-2 text-xs sm:text-sm text-foreground/85 leading-relaxed">
          {renderInline(line)}
        </p>
      );
      i++;
    }

    return parsedNodes;
  }, [content]);

  return <div className={`veyra-markdown leading-relaxed ${className}`}>{elements}</div>;
}
