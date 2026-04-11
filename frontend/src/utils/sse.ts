export interface SSEEvent {
  eventType: string
  data: Record<string, unknown>
  raw: string
}

function normalizeLines(chunk: string): string[] {
  return chunk
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}

function parseChunk(chunk: string): SSEEvent | null {
  const lines = normalizeLines(chunk)
  const eventLine = lines.find((line) => line.startsWith('event: '))
  const sseEvent = eventLine ? eventLine.slice(7).trim() : ''
  const dataLines = lines.filter((line) => line.startsWith('data: '))
  if (dataLines.length === 0) return null

  const raw = dataLines.map((line) => line.slice(6)).join('\n')

  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>
    const eventType = String(parsed.event || parsed.type || sseEvent || 'message')
    return { eventType, data: parsed, raw }
  } catch {
    if (sseEvent === 'heartbeat' || raw === 'keepalive') {
      return { eventType: 'heartbeat', data: {}, raw }
    }
    return null
  }
}

export function parseSSELines(
  buffer: string,
  lines: string[],
): { event: SSEEvent | null; remainingBuffer: string } {
  const remainingBuffer = buffer

  for (const chunk of lines) {
    if (!chunk.trim()) continue
    const event = parseChunk(chunk)
    if (event) {
      return {
        event,
        remainingBuffer,
      }
    }
  }

  return { event: null, remainingBuffer }
}

export async function* parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  decoder: TextDecoder,
): AsyncGenerator<SSEEvent, void, unknown> {
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const chunks = buffer.split(/\r?\n\r?\n/)
    buffer = chunks.pop() || ''

    for (const chunk of chunks) {
      const event = parseChunk(chunk)
      if (event) {
        yield event
      }
    }
  }

  if (buffer.trim()) {
    const event = parseChunk(buffer)
    if (event) {
      yield event
    }
  }
}
