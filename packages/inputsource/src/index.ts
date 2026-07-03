/**
 * @akasara/inputsource — modality-agnostic input adapter layer.
 *
 * Rule: nothing downstream of RawExpression may know or care which
 * modality produced it. The `modality` field exists for provenance
 * and analytics only, never for branching business logic.
 */

export type Modality = "text" | "voice" | "neural";

export interface RawExpression {
  modality: Modality;
  /** Text-normalized content. Always the same shape regardless of source. */
  payload: string;
  /** Source's own confidence in the transcription/decoding, 0..1. */
  confidence: number;
  /** Capture time, epoch milliseconds. */
  ts: number;
}

export interface InputSource {
  readonly modality: Modality;
  /** Resolves with the next completed expression from this source. */
  capture(): Promise<RawExpression>;
}

/** Collapse whitespace and trim. Every driver must emit normalized payloads. */
export function normalize(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

/**
 * TextInput — wraps any place text arrives (a form field, a CLI, stdin).
 * The host calls submit(); consumers await capture(). Submissions that
 * arrive before anyone is waiting are buffered in order.
 */
export class TextInput implements InputSource {
  readonly modality = "text" as const;
  private buffer: RawExpression[] = [];
  private waiters: Array<(e: RawExpression) => void> = [];

  submit(text: string, confidence = 1): RawExpression {
    const expr: RawExpression = {
      modality: this.modality,
      payload: normalize(text),
      confidence,
      ts: Date.now(),
    };
    const waiter = this.waiters.shift();
    if (waiter) waiter(expr);
    else this.buffer.push(expr);
    return expr;
  }

  capture(): Promise<RawExpression> {
    const buffered = this.buffer.shift();
    if (buffered) return Promise.resolve(buffered);
    return new Promise((resolve) => this.waiters.push(resolve));
  }
}

/** One voice capture = one transcription. */
export interface Transcriber {
  (): Promise<{ text: string; confidence?: number }>;
}

/**
 * VoiceInput — wraps any speech-to-text backend behind a Transcriber
 * function: Evosub's whisper_service on a server, the Web Speech API in
 * a browser, or a mock in tests. The library stays zero-dependency.
 */
export class VoiceInput implements InputSource {
  readonly modality = "voice" as const;

  constructor(private transcribe: Transcriber) {}

  async capture(): Promise<RawExpression> {
    const { text, confidence } = await this.transcribe();
    return {
      modality: this.modality,
      payload: normalize(text),
      confidence: confidence ?? 1,
      ts: Date.now(),
    };
  }
}

/**
 * NeuralInput — deliberate day-1 stub. It exists so the seam is real:
 * every consumer is already written against InputSource, so when a
 * neural-input developer API ships (Apple opening BCI HID beyond
 * Switch Control, a Merge/OpenAI API, etc.), implementing this class
 * is the ONLY change required.
 *
 * Note: today's Apple BCI HID path (Synchron -> Switch Control) surfaces
 * as ordinary selection/keyboard events, so it already flows through
 * TextInput. This driver is reserved for genuinely semantic neural APIs.
 */
export class NeuralInput implements InputSource {
  readonly modality = "neural" as const;

  capture(): Promise<RawExpression> {
    return Promise.reject(
      new Error(
        "NeuralInput is not implemented yet: no platform exposes a neural-input developer API. " +
          "Escalation triggers: Apple opens BCI input to general app APIs; any vendor ships a neural-input dev API."
      )
    );
  }
}
