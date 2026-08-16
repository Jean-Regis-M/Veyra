import fs from "fs/promises";
import path from "path";
import { MarkdownViewer } from "@/components/MarkdownViewer";
import { Header } from "@/components/Header";

async function getDocContent() {
  const filePath = path.join(process.cwd(), "site.md");
  try {
    return await fs.readFile(filePath, "utf-8");
  } catch {
    return "# VEYRA Documentation\n\nDocumentation file `site.md` could not be loaded.";
  }
}

export default async function DocsPage() {
  const content = await getDocContent();

  return (
    <div className="flex-1 pt-24 pb-20 veyra-hero-bg min-h-screen">
      <Header />

      <div className="mx-auto max-w-4xl px-4 sm:px-6">
        <div className="veyra-glass p-6 sm:p-10 my-4 shadow-2xl">
          <MarkdownViewer content={content} />
        </div>
      </div>
    </div>
  );
}
