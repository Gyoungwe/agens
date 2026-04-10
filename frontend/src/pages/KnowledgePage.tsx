import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { knowledgeApi } from '@/api'
import { Header } from '@/components/layout'
import { ImportDialog } from '@/components/knowledge/ImportDialog'
import { Plus, FileText, Search, BookOpen } from 'lucide-react'

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
          <div className="flex justify-between items-center mb-8">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <BookOpen className="w-6 h-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Manage your knowledge base
                </p>
                <p className="text-xs text-muted-foreground/60 font-mono">
                  {filteredDocs?.length || 0} documents indexed
                </p>
              </div>
            </div>
            <div className="flex gap-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="text"
                  placeholder="Search documents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-64 pl-10 pr-4 py-2.5 rounded-xl border border-border/50 bg-card text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/50 transition-all"
                />
              </div>
              <button
                onClick={() => setImportDialogOpen(true)}
                className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-primary to-primary/80 text-primary-foreground hover:shadow-lg hover:shadow-primary/25 hover:scale-105 transition-all duration-200 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                Import Document
              </button>
            </div>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-20">
              <div className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
          ) : filteredDocs?.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center">
                <BookOpen className="w-10 h-10 text-primary" />
              </div>
              <h3 className="text-xl font-semibold mb-2">No Documents</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Import a document to build your knowledge base
              </p>
              <button
                onClick={() => setImportDialogOpen(true)}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-primary to-primary/80 text-primary-foreground hover:shadow-lg hover:shadow-primary/25 transition-all duration-200 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                Import Your First Document
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredDocs?.map((doc: { id: string; filename: string; owner: string; source: string; created_at: string }) => (
                <div
                  key={doc.id}
                  className="glass-card rounded-xl p-4 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 cursor-pointer"
                >
                  <div className="flex items-start gap-4">
                    <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary/20 to-cta/20 flex items-center justify-center flex-shrink-0">
                      <FileText className="w-6 h-6 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold truncate text-foreground">{doc.filename}</h3>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span className="font-mono">Owner: {doc.owner}</span>
                        <span className="font-mono">Source: {doc.source}</span>
                        <span className="font-mono">{new Date(doc.created_at).toLocaleDateString()}</span>
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
