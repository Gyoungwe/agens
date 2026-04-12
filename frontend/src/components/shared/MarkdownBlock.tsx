import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'

interface MarkdownBlockProps {
  content: string
  className?: string
}

export function MarkdownBlock({ content, className = '' }: MarkdownBlockProps) {
  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert prose-headings:text-foreground prose-p:text-foreground prose-li:text-foreground prose-strong:text-foreground prose-code:text-emerald-600 dark:prose-code:text-emerald-400 prose-pre:bg-slate-900/85 prose-pre:text-slate-100 prose-pre:rounded-lg prose-pre:p-3 ${className}`}>
      <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{content || ''}</ReactMarkdown>
    </div>
  )
}
