"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, Dna } from "lucide-react";

interface HeaderProps {
  online?: boolean | null;
}

export function Header({ online = true }: HeaderProps) {
  const pathname = usePathname();

  const navItems = [
    { label: "Overview", href: "/" },
    { label: "Analyze", href: "/analyze" },
    { label: "VEYRA Chat", href: "/chat" },
    { label: "Docs", href: "/docs" },
    { label: "Raw API", href: "/raw" },
  ];

  return (
    <header className="fixed top-4 inset-x-0 z-50 px-4 sm:px-6 pointer-events-none">
      <div className="veyra-glass mx-auto max-w-5xl px-5 h-14 flex items-center justify-between rounded-full! pointer-events-auto shadow-2xl">
        {/* Brand Logo */}
        <Link
          href="/"
          className="flex items-center gap-2.5 font-display text-sm font-semibold tracking-wide text-foreground hover:opacity-90 transition-opacity"
        >
          <span className="relative flex h-8 w-8 shrink-0 items-center justify-center">
            {/* plain <img>, not next/image: local SVGs need images.dangerouslyAllowSVG
                to go through the optimizer, which isn't worth enabling for one icon */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/veyra-icon.svg"
              alt="VEYRA"
              width={32}
              height={32}
              className="h-8 w-8 rounded-[9px] shadow-[0_2px_10px_rgba(74,63,143,0.35)]"
            />
            <span
              className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-[#0a0d16] ${
                online === false
                  ? "bg-risk-high shadow-[0_0_8px_rgba(248,113,113,0.8)]"
                  : "veyra-pulse-dot bg-primary shadow-[0_0_10px_rgba(56,189,248,0.8)]"
              }`}
            />
          </span>
          <span className="tracking-wider font-bold">VEYRA</span>
          <span className="hidden sm:inline font-mono text-[10px] text-muted/70 tracking-widest uppercase border-l border-border/60 pl-2">
            Genomic Intelligence
          </span>
        </Link>

        {/* Unified Navigation Links */}
        <nav className="flex items-center gap-1 sm:gap-2">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || (item.href === "/chat" && pathname === "/midend");

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                  isActive
                    ? "bg-primary/20 text-primary border border-primary/40 font-semibold shadow-[0_0_12px_rgba(56,189,248,0.25)]"
                    : "text-muted hover:text-foreground hover:bg-white/5 border border-transparent"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right CTA / Quick Action */}
        <div className="hidden md:flex items-center gap-2">
          {pathname !== "/analyze" && (
            <Link
              href="/analyze"
              className="inline-flex items-center gap-1.5 rounded-full bg-linear-to-r from-primary to-secondary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-95 transition-opacity shadow-md"
            >
              <Dna size={13} />
              <span>Analyze Locus</span>
            </Link>
          )}
          {pathname === "/analyze" && (
            <Link
              href="/chat"
              className="inline-flex items-center gap-1.5 rounded-full bg-linear-to-r from-ai to-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground hover:opacity-95 transition-opacity shadow-md"
            >
              <Sparkles size={13} />
              <span>Open VEYRA Chat</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
