import { useState, useEffect } from 'react'

interface StreamingTextProps {
  text: string
  speed?: number
}

export function StreamingText({ text, speed = 20 }: StreamingTextProps) {
  const [displayedText, setDisplayedText] = useState('')

  useEffect(() => {
    setDisplayedText('')
    let index = 0

    const interval = setInterval(() => {
      if (index < text.length) {
        setDisplayedText(text.slice(0, index + 1))
        index++
      } else {
        clearInterval(interval)
      }
    }, speed)

    return () => clearInterval(interval)
  }, [text, speed])

  return <span>{displayedText}</span>
}
