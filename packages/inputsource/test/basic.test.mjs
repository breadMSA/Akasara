import assert from "node:assert/strict";
import { test } from "node:test";
import { TextInput, VoiceInput, NeuralInput, normalize } from "../dist/index.js";

test("normalize collapses whitespace", () => {
  assert.equal(normalize("  hello \n  world\t"), "hello world");
});

test("TextInput buffers submits that arrive before capture", async () => {
  const src = new TextInput();
  src.submit("first");
  src.submit("second");
  assert.equal((await src.capture()).payload, "first");
  assert.equal((await src.capture()).payload, "second");
});

test("TextInput resolves a pending capture on submit", async () => {
  const src = new TextInput();
  const pending = src.capture();
  src.submit("  spaced   out  ");
  const expr = await pending;
  assert.equal(expr.payload, "spaced out");
  assert.equal(expr.modality, "text");
  assert.equal(expr.confidence, 1);
  assert.ok(typeof expr.ts === "number" && expr.ts > 0);
});

test("VoiceInput wraps a transcriber and keeps its confidence", async () => {
  const src = new VoiceInput(async () => ({ text: "spoken  words", confidence: 0.8 }));
  const expr = await src.capture();
  assert.deepEqual(
    { modality: expr.modality, payload: expr.payload, confidence: expr.confidence },
    { modality: "voice", payload: "spoken words", confidence: 0.8 }
  );
});

test("NeuralInput rejects with escalation triggers", async () => {
  await assert.rejects(new NeuralInput().capture(), /not implemented/i);
});
