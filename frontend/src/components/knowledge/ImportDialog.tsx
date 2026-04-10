import { useState, useEffect } from 'react'
import { X, Loader2, CheckCircle2, Circle, AlertCircle } from 'lucide-react'

interface ImportDialogProps {
  open: boolean
  onClose: () => void
  onImport: () => void
}

type ImportStatus = 'idle' | 'parsing' | 'chunking' | 'vectorizing' | 'done' | 'error'

interface ProgressItem {
  status: 'pending' | 'active' | 'done' | 'error'
  message: string
}

export function ImportDialog({ open, onClose, onImport }: ImportDialogProps) {
  const [mode, setMode] = useState<'url' | 'text'>('text')
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [filename, setFilename] = useState('')
  const [isImporting, setIsImporting] = useState(false)
  const [progress, setProgress] = useState<ProgressItem[]>([
    { status: 'pending', message: 'Waiting...' },
  ])

  const steps: { key: Exclude<ImportStatus, 'idle' | 'error' | 'done'>; label: string }[] = [
    { key: 'parsing', label: 'Parsing document' },
    { key: 'chunking', label: 'Chunking text' },
    { key: 'vectorizing', label: 'Generating embeddings' },
  ]

  useEffect(() => {
    if (isImporting) {
      setProgress(steps.map((step) => ({ status: 'active', message: step.label })))

      let currentStep = 0
      const interval = setInterval(() => {
        if (currentStep < steps.length) {
          setProgress((prev) =>
            prev.map((item, i) =>
              i === currentStep ? { ...item, status: 'done' } : item
            )
          )
          if (currentStep < steps.length - 1) {
            setProgress((prev) =>
              prev.map((item, i) =>
                i === currentStep + 1 ? { ...item, status: 'active' } : item
              )
            )
          }
          currentStep++
        } else {
          clearInterval(interval)
          setIsImporting(false)
          setProgress((prev) =>
            prev.map((item) =>
              item.status === 'active' ? { ...item, status: 'done' } : item
            )
          )
          onImport()
        }
      }, 1500)
    }
  }, [isImporting])

  const handleImport = async () => {
    const content = mode === 'url' ? url : text
    if (!content.trim() || !filename.trim()) return

    setIsImporting(true)
    setProgress(steps.map((step) => ({ status: 'pending', message: step.label })))
  }

  const StatusIcon = ({ status }: { status: ProgressItem['status'] }) => {
    switch (status) {
      case 'done':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />
      case 'active':
        return <Loader2 className="w-4 h-4 animate-spin text-primary" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-destructive" />
      default:
        return <Circle className="w-4 h-4 text-muted-foreground" />
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card rounded-xl shadow-xl w-full max-w-lg p-6 z-10">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="w-4 h-4" />
        </button>

        <h3 className="text-lg font-semibold mb-4">Import Document</h3>

        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode('text')}
            className={`flex-1 px-4 py-2 text-sm rounded-lg border ${
              mode === 'text'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'border-border hover:bg-secondary'
            }`}
          >
            Text Input
          </button>
          <button
            onClick={() => setMode('url')}
            className={`flex-1 px-4 py-2 text-sm rounded-lg border ${
              mode === 'url'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'border-border hover:bg-secondary'
            }`}
          >
            URL Import
          </button>
        </div>

        {mode === 'url' ? (
          <input
            type="url"
            placeholder="https://example.com/document.pdf"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full px-4 py-3 rounded-lg border border-input bg-background mb-4"
          />
        ) : (
          <textarea
            placeholder="Paste document content here..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            className="w-full px-4 py-3 rounded-lg border border-input bg-background resize-none mb-4"
          />
        )}

        <input
          type="text"
          placeholder="Filename (e.g., document.pdf)"
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          className="w-full px-4 py-3 rounded-lg border border-input bg-background mb-4"
        />

        {isImporting && (
          <div className="mb-4 space-y-2">
            {progress.map((item, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <StatusIcon status={item.status} />
                <span
                  className={
                    item.status === 'done'
                      ? 'text-green-600'
                      : item.status === 'active'
                      ? 'text-primary'
                      : 'text-muted-foreground'
                  }
                >
                  {item.message}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-secondary transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleImport}
            disabled={isImporting || !filename.trim() || (!url && !text)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {isImporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Importing...
              </>
            ) : (
              'Import'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
