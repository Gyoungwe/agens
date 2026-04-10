export interface SSEEvent {
  eventType: string
  data: Record<string, unknown>
  raw: string
}

export function parseSSELines(
  buffer: string,
  lines: string[],
): { event: SSEEvent | null; remainingBuffer: string } {
  const remainingBuffer = buffer

  for (const chunk of lines) {
    if (!chunk.trim()) continue

    const lineStr = chunk.trim()
    const lines_inner = lineStr.split('\r\n').map((l) => l.trim())
    const eventLine = lines_inner.find((l) => l.startsWith('event: '))
    const sseEvent = eventLine ? eventLine.slice(7).trim() : ''
    const dataLine = lines_inner.find((l) => l.startsWith('data: '))
    if (!dataLine) continue

    const raw = dataLine.slice(6)
    try {
      const parsed = JSON.parse(raw)
      const eventType = parsed.event || parsed.type || sseEvent
      return {
        event: { eventType, data: parsed, raw },
        remainingBuffer,
      }
    } catch {
      // non-JSON SSE payload (e.g., heartbeat)
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
    const chunks = buffer.split('\r\n\r\n')
    buffer = chunks.pop() || ''

    for (const chunk of chunks) {
      const lines_inner = chunk.split('\r\n').map((l) => l.trim())
      const eventLine = lines_inner.find((l) => l.startsWith('event: '))
      const sseEvent = eventLine ? eventLine.slice(7).trim() : ''
      const dataLine = lines_inner.find((l) => l.startsWith('data: '))
      if (!dataLine) continue

      const raw = dataLine.slice(6)
      try {
        const parsed = JSON.parse(raw)
        const eventType = parsed.event || parsed.type || sseEvent
        yield { eventType, data: parsed, raw }
      } catch {
        // non-JSON SSE payload
      }
    }
  }
}
