import ReactMarkdown from 'react-markdown'

export default function ChatMarkdown({ children }) {
  return (
    <div className="chat-md">
      <ReactMarkdown
        components={{
          a: ({ href, children: linkChildren }) => (
            <a href={href} target="_blank" rel="noreferrer">
              {linkChildren}
            </a>
          ),
        }}
      >
        {children || ''}
      </ReactMarkdown>
    </div>
  )
}
