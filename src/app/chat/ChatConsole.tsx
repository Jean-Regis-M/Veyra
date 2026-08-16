"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  Plus,
  Send,
  X,
  FileCode,
  FileSpreadsheet,
  AlertCircle,
  MessageSquare,
  Dna,
  ArrowRight,
  BookOpen,
  Sparkles,
} from "lucide-react";
import {
  buildSessionHandbook,
  checkMidendHealth,
  createConversation,
  ExecutionStatus,
  listSkills,
  listMidendTools,
  pollExecution,
  postConversationMessage,
  sendChatMessage,
  SkillMetadata,
  uploadInputFile,
  uploadCalibrationFile,
  ValidatedInputFile,
} from "@/lib/midend";
import { ExecutionActivity } from "@/components/execution";
import { DnaAnalysisPanel, AnalysisContextData } from "@/components/DnaAnalysisPanel";
import { MarkdownViewer } from "@/components/MarkdownViewer";
import { Header } from "@/components/Header";

interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  executionId?: string;
  executionStatus?: ExecutionStatus;
  evidence?: ExecutionStatus["tool_calls"];
  errors?: string[];
  isRunning?: boolean;
  attachedInput?: ValidatedInputFile | null;
}

const QUICK_PROMPTS = [
  "Find candidate SpCas9 cutting sites",
  "What are the strongest candidates and why?",
  "Explain the off-target specificity",
  "What is the exact cleavage cut position?",
];

export default function ChatConsole() {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [online, setOnline] = useState<boolean | null>(null);
  const [skills, setSkills] = useState<SkillMetadata[]>([]);
  const [toolCount, setToolCount] = useState(0);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  // File Attachment State
  const [attachedFile, setAttachedFile] = useState<ValidatedInputFile | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [fileUploadError, setFileUploadError] = useState<string | null>(null);

  // DNA & Analysis Context Panel
  const [analysisContext, setAnalysisContext] = useState<AnalysisContextData | null>(null);
  const [sidePanelOpen, setSidePanelOpen] = useState(false);
  const [handbookOpen, setHandbookOpen] = useState(false);
  const [handbookText, setHandbookText] = useState<string | null>(null);

  const autoStartContinuedSession = useCallback(
    async (contextData: AnalysisContextData, activeSkills: SkillMetadata[], activeTools: number) => {
      setStarting(true);
      const conv = await createConversation();
      if (!conv.ok) {
        setStartError(conv.error);
        setStarting(false);
        return;
      }

      const seqSummary = `Target Sequence (${contextData.sequence?.length || 0} bp) with ${
        contextData.candidates?.length || 0
      } evaluated guide candidates. Top candidate: ${
        contextData.selectedCandidate?.protospacer || "N/A"
      } (PAM: ${contextData.selectedCandidate?.pam || "NGG"}, Rank #${
        contextData.selectedCandidate?.rank || 1
      })`;

      const book = buildSessionHandbook(activeSkills, activeTools, seqSummary);
      await postConversationMessage(conv.data.conversation_id, book, "system");

      setHandbookText(book);
      setConversationId(conv.data.conversation_id);
      setTurns([
        {
          role: "assistant",
          content: `I've loaded your continued analysis for the target locus (${contextData.sequence?.length || 0} bp, ${
            contextData.candidates?.length || 0
          } candidates evaluated). Top candidate is **${
            contextData.selectedCandidate?.protospacer || "active"
          }**.\n\nYou can ask me to explain off-target risk, inspect cut sites, compare candidates, or attach experimental calibration data.`,
        },
      ]);
      setStarting(false);
    },
    []
  );

  // Check health and available tools
  useEffect(() => {
    void checkMidendHealth().then((r) => setOnline(r.ok));
    void listSkills().then((r) => {
      if (r.ok) setSkills(r.data.skills);
    });
    void listMidendTools().then((r) => {
      if (r.ok) setToolCount(r.data.total_tools);
    });
  }, []);

  // Check for continuation from /analyze session
  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = sessionStorage.getItem("veyra_analysis_continuation");
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as AnalysisContextData;
        sessionStorage.removeItem("veyra_analysis_continuation");
        Promise.resolve().then(() => {
          setAnalysisContext(parsed);
          setSidePanelOpen(true);
          void autoStartContinuedSession(parsed, skills, toolCount);
        });
      } catch {
        // ignore parse error
      }
    }
  }, [skills, toolCount, autoStartContinuedSession]);

  async function startSession() {
    setStarting(true);
    setStartError(null);
    const conv = await createConversation();
    if (!conv.ok) {
      setStartError(conv.error);
      setStarting(false);
      return;
    }
    const book = buildSessionHandbook(skills, toolCount);
    const posted = await postConversationMessage(conv.data.conversation_id, book, "system");
    if (!posted.ok) {
      setStartError(posted.error);
      setStarting(false);
      return;
    }
    setHandbookText(book);
    setConversationId(conv.data.conversation_id);
    setTurns([]);
    setStarting(false);
  }

  async function handleFileUpload(file: File) {
    setUploadingFile(true);
    setFileUploadError(null);

    const isCalibration = file.name.endsWith(".csv") || file.name.endsWith(".tsv") || file.name.endsWith(".tab");
    if (isCalibration) {
      const calibRes = await uploadCalibrationFile(file);
      setUploadingFile(false);
      if (!calibRes.ok) {
        setFileUploadError(calibRes.error);
        return;
      }
      setAttachedFile({
        input_id: calibRes.data.input_id,
        filename: calibRes.data.filename,
        format: calibRes.data.format,
        detected_format: calibRes.data.format,
        input_class: "calibration_input",
        size_bytes: calibRes.data.size_bytes,
        record_count: calibRes.data.row_count,
        sequence_count: 0,
        validation_status: calibRes.data.validation_status,
        backend_operation: "calibration",
        columns: calibRes.data.columns,
        column_count: calibRes.data.column_count,
        row_count: calibRes.data.row_count,
        sample_count: calibRes.data.sample_count,
      });
      return;
    }

    const result = await uploadInputFile(file);
    setUploadingFile(false);
    if (!result.ok) {
      setFileUploadError(result.error);
      return;
    }

    setAttachedFile(result.data);
    setAnalysisContext((prev) => ({
      ...prev,
      filename: result.data.filename,
      inputId: result.data.input_id,
    }));
    setSidePanelOpen(true);
  }

  async function send(messageText?: string) {
    const textToSend = (messageText ?? input).trim();
    if (!conversationId || !textToSend || sending) return;

    setInput("");
    setSending(true);

    const inputIds = attachedFile ? [attachedFile.input_id] : [];
    const currentAttached = attachedFile;

    const userTurn: ChatTurn = {
      role: "user",
      content: textToSend,
      attachedInput: currentAttached,
    };
    setTurns((t) => [...t, userTurn]);

    const started = await sendChatMessage(textToSend, conversationId, inputIds);
    if (!started.ok) {
      setTurns((t) => [
        ...t,
        { role: "assistant", content: `(Request failed: ${started.error})` },
      ]);
      setSending(false);
      return;
    }

    const execId = started.data.execution_id;
    setAnalysisContext((prev) => ({
      ...prev,
      executionId: execId,
    }));

    setTurns((t) => [
      ...t,
      {
        role: "assistant",
        content: "",
        executionId: execId,
        isRunning: true,
      },
    ]);

    const result = await pollExecution(execId);
    if (!result.ok) {
      setTurns((prev) => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
          next[lastIdx] = {
            role: "assistant",
            content: `(${result.error})`,
            executionId: execId,
            isRunning: false,
          };
        }
        return next;
      });
    } else {
      setTurns((prev) => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && next[lastIdx].role === "assistant") {
          next[lastIdx] = {
            role: "assistant",
            content: result.data.assistant_output ?? "(no output generated)",
            executionId: execId,
            executionStatus: result.data,
            evidence: result.data.tool_calls,
            errors: result.data.errors,
            isRunning: false,
          };
        }
        return next;
      });

      setAnalysisContext((prev) => ({
        ...prev,
        executionId: execId,
        executionStatus: result.data,
      }));
    }
    setSending(false);
  }

  return (
    <div className="flex-1 pt-24 pb-12 veyra-hero-bg min-h-screen flex flex-col">
      <Header online={online} />

      {/* Main Layout Area */}
      <div className="mx-auto max-w-6xl w-full px-4 sm:px-6 flex-1 flex gap-6 mt-2">
        {/* Left / Main Conversation Area */}
        <div className="flex-1 flex flex-col min-w-0 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-display text-2xl font-semibold text-foreground flex items-center gap-2">
                <MessageSquare size={22} className="text-primary" />
                VEYRA Intelligence
              </h1>
              <p className="mt-1 text-xs sm:text-sm text-muted">
                Grounded conversational AI orchestration over deterministic CRISPR PAM, cleavage geometry, and CFD algorithms.
              </p>
            </div>

            {conversationId && (
              <button
                type="button"
                onClick={() => setSidePanelOpen((v) => !v)}
                className="hidden lg:inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-mono text-primary hover:bg-primary/20 transition-colors cursor-pointer"
              >
                <Dna size={14} />
                <span>{sidePanelOpen ? "Hide DNA Panel" : "Show DNA Panel"}</span>
              </button>
            )}
          </div>

          {!conversationId ? (
            <div className="veyra-glass p-8 space-y-6 text-center max-w-xl mx-auto my-auto">
              <div className="h-12 w-12 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center mx-auto text-primary">
                <Sparkles size={24} />
              </div>
              <div className="space-y-2">
                <h2 className="font-display text-lg font-semibold text-foreground">Start a VEYRA Session</h2>
                <p className="text-xs text-muted leading-relaxed">
                  Connect to the {toolCount} live backend tools and {skills.length} specialized skills. Literature-grounded evidence and deterministic verification are loaded into the session.
                </p>
              </div>

              {startError && (
                <div className="rounded-lg border border-risk-high/40 bg-risk-high/10 p-3 text-xs text-risk-high flex items-center gap-2">
                  <AlertCircle size={15} />
                  <span>{startError}</span>
                </div>
              )}

              <button
                onClick={startSession}
                disabled={starting || online === false}
                className="rounded-full bg-linear-to-r from-primary to-secondary px-8 py-3 text-sm font-semibold text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50 shadow-lg cursor-pointer"
              >
                {starting ? "Initializing Session…" : "Start VEYRA Session"}
              </button>

              {online === false && (
                <p className="text-xs text-risk-high">VEYRA midend service unreachable on port 8080.</p>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col space-y-3 min-w-0">
              {/* Handbook / Grounding Info Banner */}
              <div className="veyra-glass px-4 py-2 flex items-center justify-between text-xs">
                <span className="font-mono text-[11px] text-muted flex items-center gap-1.5">
                  <BookOpen size={13} className="text-primary" />
                  Grounded Evidence Session Active ({toolCount} tools)
                </span>
                <button
                  type="button"
                  onClick={() => setHandbookOpen((v) => !v)}
                  className="font-mono text-[10px] uppercase text-primary hover:underline"
                >
                  {handbookOpen ? "Hide Handbook" : "View Orientation Rules"}
                </button>
              </div>

              {handbookOpen && handbookText && (
                <div className="veyra-glass p-4 text-xs font-mono max-h-60 overflow-y-auto">
                  <pre className="text-muted whitespace-pre-wrap">{handbookText}</pre>
                </div>
              )}

              {/* Chat Messages Container */}
              <div className="veyra-glass p-4 sm:p-5 flex-1 overflow-y-auto space-y-4 min-h-[360px] max-h-[600px] custom-scrollbar">
                {turns.length === 0 && (
                  <div className="p-8 text-center space-y-3 my-auto">
                    <p className="text-sm text-foreground/80 font-medium">Session initialized. How can VEYRA assist your CRISPR workflow today?</p>
                    <p className="text-xs text-muted max-w-md mx-auto">
                      Attach a target FASTA/GenBank file with the <span className="text-primary font-bold">+</span> button below, or ask a question directly.
                    </p>
                    <div className="flex flex-wrap justify-center gap-2 pt-2">
                      {QUICK_PROMPTS.map((prompt, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => void send(prompt)}
                          className="rounded-full border border-border bg-black/30 px-3.5 py-1.5 text-xs text-muted hover:text-foreground hover:border-primary/50 transition-colors"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {turns.map((turn, idx) => (
                  <div key={idx} className="space-y-2 animate-in fade-in duration-150">
                    <div className="flex items-center justify-between">
                      <span
                        className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-wider font-semibold ${
                          turn.role === "user"
                            ? "text-muted border-border-strong bg-white/5"
                            : "text-primary border-primary/40 bg-primary/10"
                        }`}
                      >
                        {turn.role === "user" ? "You" : "VEYRA Intelligence"}
                      </span>
                    </div>

                    {/* Attached file chip on user turn */}
                    {turn.attachedInput && (
                      <div className="inline-flex items-center gap-1.5 rounded-lg border border-border/50 bg-black/40 px-3 py-1 text-xs font-mono text-muted">
                        <FileCode size={13} className="text-primary" />
                        <span>{turn.attachedInput.filename}</span>
                        <span className="text-[10px] text-muted/70">
                          ({turn.attachedInput.detected_format}, {turn.attachedInput.record_count} records)
                        </span>
                      </div>
                    )}

                    {/* Content */}
                    {turn.content ? (
                      <div className="text-sm text-foreground/90 leading-relaxed">
                        <MarkdownViewer content={turn.content} />
                      </div>
                    ) : turn.isRunning ? (
                      <p className="text-sm text-primary font-mono animate-pulse flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary animate-ping" />
                        Analyzing sequence and executing deterministic tools...
                      </p>
                    ) : null}

                    {/* Expandable Live Tool / Execution Activity */}
                    {turn.executionId && (
                      <ExecutionActivity
                        executionId={turn.executionId}
                        initialData={turn.executionStatus}
                        live={turn.isRunning}
                        defaultCollapsed={!turn.isRunning}
                        onFinished={(updatedStatus) => {
                          setTurns((prev) => {
                            const next = [...prev];
                            const tIdx = next.findIndex((t) => t.executionId === turn.executionId);
                            if (tIdx >= 0) {
                              next[tIdx] = {
                                ...next[tIdx],
                                isRunning: false,
                                executionStatus: updatedStatus,
                                content: next[tIdx].content || updatedStatus.assistant_output || (updatedStatus.status === "failed" ? "(Execution failed)" : "(Execution finished)"),
                              };
                            }
                            return next;
                          });
                        }}
                      />
                    )}

                    {/* Assistant Follow-up Action / Continue in Chat */}
                    {turn.role === "assistant" && !turn.isRunning && turn.content && (
                      <div className="pt-1 flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => {
                            setInput("Can you provide more details on this specific candidate?");
                          }}
                          className="text-[11px] font-mono text-primary/80 hover:text-primary hover:underline flex items-center gap-1 cursor-pointer"
                        >
                          <span>Continue this in chat</span>
                          <ArrowRight size={12} />
                        </button>
                      </div>
                    )}

                    {turn.errors && turn.errors.length > 0 && (
                      <p className="text-xs text-risk-high">{turn.errors.join("; ")}</p>
                    )}
                  </div>
                ))}
              </div>

              {/* Upload Error Display */}
              {fileUploadError && (
                <div className="rounded-lg border border-risk-high/40 bg-risk-high/10 px-3.5 py-2 text-xs text-risk-high flex items-center justify-between">
                  <span>{fileUploadError}</span>
                  <button type="button" onClick={() => setFileUploadError(null)}>
                    <X size={14} />
                  </button>
                </div>
              )}

              {/* Attached File Chip (Pending Send) */}
              {attachedFile && (
                <div className="veyra-glass px-3.5 py-1.5 flex items-center justify-between text-xs font-mono text-foreground border-primary/30">
                  <div className="flex items-center gap-2 truncate">
                    {attachedFile.input_class === "calibration_input" ? (
                      <FileSpreadsheet size={15} className="text-secondary shrink-0" />
                    ) : (
                      <FileCode size={15} className="text-primary shrink-0" />
                    )}
                    <span className="truncate font-semibold">{attachedFile.filename}</span>
                    <span className="rounded bg-primary/20 text-primary px-1.5 py-0.2 text-[9px] uppercase">
                      {attachedFile.detected_format}
                    </span>
                    <span className="text-[10px] text-muted">
                      {attachedFile.input_class === "calibration_input"
                        ? `${attachedFile.sample_count || attachedFile.row_count} rows`
                        : `${attachedFile.record_count} records`}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAttachedFile(null)}
                    className="text-muted hover:text-foreground p-1"
                    title="Remove attachment"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

              {/* Input Area with + Attachment Button */}
              <div className="veyra-glass p-2.5 flex items-center gap-2">
                {/* Hidden File Input */}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".fa,.fasta,.fna,.faa,.fns,.frn,.fq,.fastq,.fqr,.gb,.gbk,.gbff,.genbank,.csv,.tsv,.tab"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (file) void handleFileUpload(file);
                  }}
                />

                {/* + Attachment Button */}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingFile || sending}
                  className="h-9 w-9 shrink-0 rounded-full border border-border bg-black/40 flex items-center justify-center text-muted hover:text-primary hover:border-primary/50 transition-colors disabled:opacity-50 cursor-pointer"
                  title="Attach analysis file (FASTA, FASTQ, GenBank) or calibration dataset (CSV, TSV)"
                >
                  <Plus size={16} />
                </button>

                {/* Textarea / Input */}
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && void send()}
                  placeholder={
                    attachedFile
                      ? `Ask questions about ${attachedFile.filename}...`
                      : "Ask VEYRA about CRISPR guides, off-targets, cut positions, or attach a file (+)..."
                  }
                  className="flex-1 border-0 bg-transparent px-2 text-sm text-foreground focus:outline-none placeholder:text-muted/50"
                />

                {/* Send Button */}
                <button
                  type="button"
                  onClick={() => void send()}
                  disabled={sending || (!input.trim() && !attachedFile)}
                  className="rounded-full bg-linear-to-r from-primary to-secondary px-5 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-40 flex items-center gap-1.5 cursor-pointer"
                >
                  <span>Send</span>
                  <Send size={13} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right / Expandable DNA & Analysis Evidence Panel */}
        {conversationId && (
          <DnaAnalysisPanel
            context={analysisContext}
            isOpen={sidePanelOpen}
            onToggle={() => setSidePanelOpen((v) => !v)}
            onSelectCandidate={(cand) => {
              setAnalysisContext((prev) => ({
                ...prev,
                selectedCandidate: cand,
              }));
            }}
          />
        )}
      </div>
    </div>
  );
}
