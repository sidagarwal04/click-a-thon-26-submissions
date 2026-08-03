import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Markdown, rendered as elements.
 *
 * Agent output is markdown, so it is parsed rather than printed. No
 * `dangerouslySetInnerHTML` and no raw-HTML plugin: model output is untrusted
 * input, and the one thing it must never be able to do is inject markup.
 *
 * The design system has no typography plugin, so element styles are supplied
 * per node here — the same tokens the rest of the product uses.
 */
export const Markdown = ({ children }: { readonly children: string }) => (
  <div className="text-sm leading-relaxed text-foreground">
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children: content }) => <p className="mb-3 last:mb-0">{content}</p>,
        h1: ({ children: content }) => (
          <h1 className="mb-3 mt-5 font-serif text-2xl font-normal first:mt-0">{content}</h1>
        ),
        h2: ({ children: content }) => (
          <h2 className="mb-3 mt-5 font-serif text-xl font-normal first:mt-0">{content}</h2>
        ),
        h3: ({ children: content }) => (
          <h3 className="mb-2 mt-5 font-mono text-[11px] font-bold uppercase tracking-[0.16em] text-primary first:mt-0">
            {content}
          </h3>
        ),
        ul: ({ children: content }) => (
          <ul className="mb-3 list-disc pl-5 marker:text-primary">{content}</ul>
        ),
        ol: ({ children: content }) => (
          <ol className="mb-3 list-decimal pl-5 marker:text-foreground-muted">{content}</ol>
        ),
        li: ({ children: content }) => <li className="mb-1">{content}</li>,
        strong: ({ children: content }) => (
          <strong className="font-semibold text-foreground">{content}</strong>
        ),
        em: ({ children: content }) => <em className="italic">{content}</em>,
        a: ({ children: content, href }) => (
          <a
            className="text-primary underline underline-offset-2"
            href={href}
            target={href?.startsWith('http') ? '_blank' : undefined}
            rel={href?.startsWith('http') ? 'noreferrer' : undefined}
          >
            {content}
          </a>
        ),
        blockquote: ({ children: content }) => (
          <blockquote className="mb-3 border-l-2 border-primary pl-4 text-foreground-muted">
            {content}
          </blockquote>
        ),
        code: ({ children: content, className }) =>
          // A fenced block arrives with a language class; an inline span does
          // not, and the two want completely different boxes.
          className ? (
            <code className="font-mono text-[12px]">{content}</code>
          ) : (
            <code className="rounded-sm bg-background-muted px-1.5 py-0.5 font-mono text-[12px] text-primary">
              {content}
            </code>
          ),
        pre: ({ children: content }) => (
          <pre className="mb-3 overflow-x-auto rounded-sm border border-border bg-background-muted p-3">
            {content}
          </pre>
        ),
        table: ({ children: content }) => (
          <div className="mb-3 overflow-x-auto">
            <table className="w-full border-collapse text-left text-[13px]">{content}</table>
          </div>
        ),
        th: ({ children: content }) => (
          <th className="border-b border-border px-3 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-foreground-muted">
            {content}
          </th>
        ),
        td: ({ children: content }) => (
          <td className="border-b border-border-subtle px-3 py-2">{content}</td>
        ),
        hr: () => <hr className="my-5 border-border" />,
      }}
    >
      {children}
    </ReactMarkdown>
  </div>
);
