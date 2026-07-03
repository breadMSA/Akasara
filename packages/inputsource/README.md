# @akasara/inputsource

Modality-agnostic input adapter layer. Everything a person expresses — typed,
spoken, and eventually decoded neurally — enters as one shape:

```ts
interface RawExpression {
  modality: "text" | "voice" | "neural";
  payload: string;      // text-normalized
  confidence: number;   // 0..1
  ts: number;           // epoch ms
}
```

**The rule:** nothing downstream of `RawExpression` knows the modality.
`modality` is provenance, never a branch condition.

## Drivers

| Driver | Status | Notes |
| --- | --- | --- |
| `TextInput` | working | host calls `submit()`, consumers `await capture()` |
| `VoiceInput` | working | wraps any `Transcriber` (whisper service, Web Speech API, mock) |
| `NeuralInput` | deliberate stub | rejects with the escalation triggers; implementing it is the *only* change needed when a neural dev API ships |

## Usage

```ts
import { TextInput, VoiceInput } from "@akasara/inputsource";

const text = new TextInput();
text.submit("hello world");
const expr = await text.capture(); // { modality: "text", payload: "hello world", ... }

const voice = new VoiceInput(async () => myWhisper.transcribeOnce());
const spoken = await voice.capture();
```

## Why the stub exists

Today's real BCI input path (Synchron implant → Apple Switch Control) surfaces
as ordinary selection/keyboard events — it already flows through `TextInput`.
`NeuralInput` is reserved for the day a platform exposes a *semantic* neural
API. Because every consumer is written against `InputSource` from day 1,
adopting that API is an adapter, not a rewrite.

Build: `npm run build` (only dev dependency is TypeScript).
