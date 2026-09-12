import { Fragment, type ReactNode } from "react";

const HTML_ENTITIES: Record<string, string> = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ",
};

export function normalizeRichText(value: string): string {
  return value
    .replace(/<\s*br\s*\/?>/gi, "\n")
    .replace(/<\s*\/\s*(p|div|li|h[1-6])\s*>/gi, "\n")
    .replace(/<\s*li(?:\s[^>]*)?>/gi, "- ")
    .replace(/<[^>]*>/g, "")
    .replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (_, entity: string) => {
      if (entity.startsWith("#x")) return String.fromCodePoint(Number.parseInt(entity.slice(2), 16));
      if (entity.startsWith("#")) return String.fromCodePoint(Number.parseInt(entity.slice(1), 10));
      return HTML_ENTITIES[entity.toLowerCase()] ?? `&${entity};`;
    })
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function inlineNodes(value: string): ReactNode[] {
  const token = /(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^)\s]+\))/g;
  return value.split(token).filter(Boolean).map((part, index) => {
    if ((part.startsWith("**") && part.endsWith("**")) || (part.startsWith("__") && part.endsWith("__"))) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    const link = /^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/.exec(part);
    if (link) return <a key={index} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>;
    return <Fragment key={index}>{part.replace(/(^|\s)[*_]+(?=\S)|(?<=\S)[*_]+(?=\s|$)/g, "$1")}</Fragment>;
  });
}

export function SafeRichText({ value, className }: { value: string; className?: string }) {
  const normalized = normalizeRichText(value);
  const blocks = normalized.split(/\n{2,}/).filter(Boolean);
  return <div className={className}>
    {blocks.map((block, blockIndex) => {
      const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
      const bullets = lines.every((line) => /^[-•]\s+/.test(line));
      if (bullets) return <ul key={blockIndex}>{lines.map((line, lineIndex) => <li key={lineIndex}>{inlineNodes(line.replace(/^[-•]\s+/, ""))}</li>)}</ul>;
      return <p key={blockIndex}>{lines.map((line, lineIndex) => <Fragment key={lineIndex}>{lineIndex > 0 && <br />}{inlineNodes(line.replace(/^#{1,6}\s+/, ""))}</Fragment>)}</p>;
    })}
  </div>;
}
