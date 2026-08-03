import type { ReactNode } from "react";

// Purpose-built for the narrator/replay output shape (backend/api/main.py's _replay_text,
// backend/narrator/narrate.py's prose) — headings ("## "), bold ("**text**"), inline code
// ("`text`"), links ("[text](url)"), and "  - " bullet lines. Not a general markdown engine;
// pulling in a full parser for a handful of known constructs would be a lot of dead weight for
// a chat panel that only ever renders our own bundle-grounded output.

const INLINE = /(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(INLINE).filter(Boolean).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={key} className="md-code">{part.slice(1, -1)}</code>;
    }
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    if (link) {
      return (
        <a key={key} href={link[2]} target="_blank" rel="noreferrer" className="md-link">
          {link[1]}
        </a>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

export function MarkdownLite({ text }: { text: string }) {
  const blocks = text.trim().split(/\n{2,}/);

  return (
    <div className="md">
      {blocks.map((block, bi) => {
        if (block.startsWith("## ")) {
          return <h4 key={bi} className="md-h">{renderInline(block.slice(3), `b${bi}`)}</h4>;
        }

        const lines = block.split("\n");
        const nodes: ReactNode[] = [];
        let para: string[] = [];
        let list: string[] = [];

        const flushPara = () => {
          if (para.length) {
            nodes.push(<p key={`p${nodes.length}`} className="md-p">{renderInline(para.join(" "), `p${nodes.length}`)}</p>);
            para = [];
          }
        };
        const flushList = () => {
          if (list.length) {
            nodes.push(
              <ul key={`l${nodes.length}`} className="md-list">
                {list.map((item, li) => <li key={li}>{renderInline(item, `l${nodes.length}-${li}`)}</li>)}
              </ul>
            );
            list = [];
          }
        };

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("- ")) {
            flushPara();
            list.push(trimmed.slice(2));
          } else if (trimmed) {
            flushList();
            para.push(trimmed);
          }
        }
        flushPara();
        flushList();

        return <div key={bi} className="md-block">{nodes}</div>;
      })}
    </div>
  );
}
