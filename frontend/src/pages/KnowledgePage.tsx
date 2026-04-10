import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { knowledgeApi } from '@/api'
import { Header } from '@/components/layout'
import { ImportDialog } from '@/components/knowledge/ImportDialog'
import { Plus, FileText, Search } from 'lucide-react'

export function KnowledgePage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [importDialogOpen, setImportDialogOpen] = useState(false)

  const { data: docsData, isLoading, refetch } = useQuery({
    queryKey: ['knowledge'],
    queryFn: async () => {
      const response = await knowledgeApi.getDocuments({ limit: 100 })
      return response.data
    },
  })

  const filteredDocs = docsData?.documents?.filter((doc: { filename: string }) =>
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full">
      <Header title="Knowledge Base" />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex justify-between items-center mb-6">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg border border-input bg-background"
              />
            </div>
            <button
              onClick={() => setImportDialogOpen(true)}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Import Document
            </button>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="loading-spinner" />
            </div>
          ) : filteredDocs?.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <div className="text-4xl mb-4">📚</div>
              <h3 className="text-lg font-medium mb-2">No documents</h3>
              <p className="text-sm">Import a document to get started</p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredDocs?.map((doc: { id: string; filename: string; owner: string; source: string; created_at: string }) => (
                <div
                  key={doc.id}
                  className="bg-card rounded-xl border border-border p-4 hover:border-primary/50 transition-colors"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
                      <FileText className="w-5 h-5 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium truncate">{doc.filename}</h3>
                      <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
                        <span>Owner: {doc.owner}</span>
                        <span>Source: {doc.source}</span>
                        <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <ImportDialog
        open={importDialogOpen}
        onClose={() => setImportDialogOpen(false)}
        onImport={() => {
          refetch()
          setImportDialogOpen(false)
        }}
      />
    </div>
  )
}
