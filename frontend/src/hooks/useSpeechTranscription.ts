import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Live transcription from the microphone, using the browser's own speech
 * recognition.
 *
 * Why this and not a transcription service: there is no API key to hold, no
 * audio leaves the page in our control, and it works offline in Chrome. What
 * it costs is browser support - this is a WebKit/Chromium feature, and Firefox
 * has none of it - so `isSupported` is part of the contract and the caller has
 * to handle its absence rather than assume a microphone.
 *
 * The recogniser emits two kinds of result. Interim results change as you keep
 * talking and are only good for showing the words appearing; final results are
 * what get committed. Only finals are handed to `onFinal`, so nothing
 * half-heard is ever written to the database.
 */

// The API is unprefixed in the spec and prefixed everywhere it actually ships.
type SpeechRecognitionLike = {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}

type SpeechRecognitionEventLike = {
  resultIndex: number
  results: ArrayLike<
    ArrayLike<{ transcript: string; confidence: number }> & { isFinal: boolean }
  >
}

function getRecognition(): SpeechRecognitionLike | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike
    webkitSpeechRecognition?: new () => SpeechRecognitionLike
  }
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition
  return Ctor ? new Ctor() : null
}

export type FinalUtterance = {
  text: string
  confidence: number | null
  /** Milliseconds from when listening started, measured by the caller's clock. */
  startMs: number
  endMs: number
}

export function useSpeechTranscription({
  lang = 'en-US',
  onFinal,
  elapsedMs,
}: {
  lang?: string
  onFinal: (utterance: FinalUtterance) => void
  /** Reads the recording clock. A function, not a value, so the recogniser's
   *  callbacks always see the current time rather than a stale closure. */
  elapsedMs: () => number
}) {
  const [isListening, setIsListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState<string | null>(null)

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const utteranceStart = useRef(0)
  const wantsToListen = useRef(false)
  const onFinalRef = useRef(onFinal)
  const elapsedRef = useRef(elapsedMs)
  useEffect(() => {
    onFinalRef.current = onFinal
    elapsedRef.current = elapsedMs
  }, [onFinal, elapsedMs])

  const isSupported = typeof window !== 'undefined' && getRecognition() !== null

  const stop = useCallback(() => {
    wantsToListen.current = false
    recognitionRef.current?.stop()
    setIsListening(false)
    setInterim('')
  }, [])

  const start = useCallback(() => {
    const recognition = getRecognition()
    if (!recognition) {
      setError('This browser cannot transcribe speech. Try Chrome or Edge.')
      return
    }

    recognition.lang = lang
    recognition.continuous = true
    recognition.interimResults = true
    utteranceStart.current = elapsedRef.current()

    recognition.onresult = (event) => {
      let pending = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        const best = result[0]
        if (result.isFinal) {
          const text = best.transcript.trim()
          if (text) {
            onFinalRef.current({
              text,
              confidence: Number.isFinite(best.confidence) ? best.confidence : null,
              startMs: utteranceStart.current,
              endMs: elapsedRef.current(),
            })
          }
          // The next utterance starts where this one ended.
          utteranceStart.current = elapsedRef.current()
        } else {
          pending += best.transcript
        }
      }
      setInterim(pending)
    }

    recognition.onerror = (event) => {
      // `no-speech` and `aborted` are routine during a quiet stretch or a
      // restart; surfacing them as errors would make the UI look broken.
      if (event.error === 'no-speech' || event.error === 'aborted') return
      setError(
        event.error === 'not-allowed'
          ? 'Microphone access was blocked. Allow it and press record again.'
          : 'Transcription stopped: %s'.replace('%s', event.error),
      )
      wantsToListen.current = false
      setIsListening(false)
    }

    recognition.onend = () => {
      // Chrome ends the session on its own after a pause. Restart so a long
      // meeting keeps transcribing instead of going quiet halfway through.
      if (wantsToListen.current) {
        try {
          recognition.start()
          return
        } catch {
          // Already restarting; the next onend will try again.
        }
      }
      setIsListening(false)
      setInterim('')
    }

    setError(null)
    wantsToListen.current = true
    recognitionRef.current = recognition
    try {
      recognition.start()
      setIsListening(true)
    } catch {
      setError('Could not start the microphone.')
    }
  }, [lang])

  // Never leave the microphone open on a page the user has left.
  useEffect(() => () => {
    wantsToListen.current = false
    recognitionRef.current?.abort()
  }, [])

  return { isSupported, isListening, interim, error, start, stop, clearError: () => setError(null) }
}
