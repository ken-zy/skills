# Prompt And Candidates

Use this reference before writing Pre/formal prompts or generating images.

## Pre

Create one independent `Pre` style-positioning image before formal candidates.

Purpose:

- prove the Xiaohongshu structure and product style direction can coexist
- lock model direction, outfit language, lighting, scene mood, color temperature, and framing density
- avoid wasting formal attempts before the style direction is concrete

Rules:

- Name this stage `Pre`.
- Do not count `Pre` as slot 01.
- Do not count `Pre` toward the final 9 images.
- If `Pre` is based on a `market-derived` Xiaohongshu source, include the selected XHS images in the prompt `ref` list and load them as visual inputs before generation. Do not rely on a text summary of the source alone.
- Move every generated Pre candidate into `style/pre-candidates/`.
- Copy the accepted candidate to `style/style-positioning-anchor.png`.
- Record the accepted Pre in `style/_ref-map.md`.
- If Pre has wrong product details, use it only for style/model/light/scene/framing. Formal product fidelity still comes only from product refs.

Light acceptance checklist:

- style line matches product positioning and Xiaohongshu structure map
- any `market-derived` XHS source named in `source_basis` is present as actual visual prompt input, or the source is downgraded to written evidence only
- outfit/scene/light can support multiple slots
- face/body/hand quality is clean enough for style anchoring
- product display area is plausible and not blocked
- no forbidden high-luxury, heavy dark, beach/boho, or cold-minimal direction

## Generation Tool Routing

Image generation always runs through Codex's built-in `$imagegen` / `image_gen` tool. The routing rules differ by which agent is driving the workflow.

### When Codex is the executing agent

- Use the `$imagegen` / `image_gen` built-in tool directly.
- Open the prompt JSON and load each `ref` image with `view_image` in the exact order they appear in the `ref` array, so Image 1 / Image 2 / ... in the prompt text match the order Codex actually saw them.
- Then call `$imagegen` with the prompt text, restating `Image 1 = ... only; Image 2 = ... only` at the top.
- After generation, move the chosen output from `$CODEX_HOME/generated_images/...` into `style/pre-candidates/` (for Pre) or `drafts/<slot-id>/` (for formal slots), then run `python3 scripts/sync_review_csv.py <note-dir>`.

### When Claude Code is the executing agent

Claude Code does not have `$imagegen` natively. Generation must go through Codex via `/ask-codex`, but the visual context still has to be primed first.

Required sequence:

1. **Load every `ref` image into the current Claude Code conversation context using the `Read` tool, in the exact order they appear in the prompt JSON's `ref` array.** This is the Claude-side equivalent of Codex's `view_image`. Order is non-negotiable: a wrong order silently re-binds Image 1 / Image 2 / ... to the wrong roles and the resulting picture will not match the prompt's role assignments.
2. Confirm that the `ref` count, the `ref_roles` count, and the number of images you actually loaded all match. If any of the three diverge, fix the prompt JSON or reload the images before continuing.
3. Build the prompt text by concatenating the prompt JSON's `prompt` field with an explicit role restatement matching the order of step 1 (`Image 1 = ... only; Image 2 = ... only; ...`).
4. Invoke `/ask-codex` with that combined prompt text. Codex receives the prompt, but the local Claude Code session is the side that holds the freshly loaded ref images, so the role restatement must be self-contained text that describes each image's job; do not assume Codex can see the same loaded images.
5. After Codex returns the generated image path(s), move the chosen output from `$CODEX_HOME/generated_images/...` (or wherever Codex saved it) into `style/pre-candidates/` (for Pre) or `drafts/<slot-id>/` (for formal slots), using the standard naming convention.
6. Run `python3 scripts/sync_review_csv.py <note-dir>` to register the new draft, then continue with the normal scoring step.

If any `ref` image cannot be loaded (missing file, broken path, unreadable format), stop and fix the asset or the JSON before invoking `/ask-codex`. Do not generate from an incomplete or wrongly-ordered visual context.

### Hand-off note

Whichever agent drives generation, the contract that "every `ref` image actually reaches the model in the order specified by the prompt" must be satisfied. The two routing modes above are equivalent in intent; only the local mechanism differs.

## Prompt Structure

For each formal slot, write one prompt JSON under `prompts/`.

Use structured prompt sections:

1. Style and intent
2. Reference role assignment matching the `ref` array order
3. Priority order
4. Reference observation rule
5. Model/outfit
6. Product visibility
7. Composition/scene/camera
8. Positive constraints and specific keep rules

Before calling generation, compare `source_basis`, `ref`, and the images loaded into context. Every visual source that contributes to a `market-derived` label must appear in all three places: named in `source_basis`, copied into a stable note-local `style/` file, and loaded as a visual input. If a Xiaohongshu source is only mentioned in research notes, it may inform written reasoning but cannot justify a `market-derived` generation label.

When using accepted Pre in a formal prompt, assign this narrow role:

```text
Image N = accepted Pre style-positioning baseline for model direction, outfit language, lighting, scene mood, color temperature, and framing density only. Do not copy or infer product structure, product color, material details, component count, or wearing proportion from this image. Product fidelity must come only from the product-ref images.
```

## Formal Candidate Iteration

Start each formal slot with candidates that use the accepted Pre plus all required refs for visible product components. Generate enough candidates to make a real choice, usually 3-5 when practical.

Score every candidate before deciding whether another candidate is needed.

If a candidate reaches the final gate, stop generating for that slot and copy it into `final/`.

If a candidate is useful but not final-ready, the **default action is NOT to feed that candidate back into the next prompt's `ref` array**. The accepted Pre (or, after a product-correct cover exists, the `series-anchor`) is the canonical anchor for every formal slot in this note — it is intentionally jewelry-free / product-correct so that product fidelity comes only from product refs.

Failed candidates may go into `review.csv` notes as written context for the next round (e.g. "previous candidate rendered necklace as mini-pearls — strengthen ribbed-glass + old-gold-spacer description"), but they should not be loaded as a visual `ref` for the next candidate. Loading a failed candidate as visual context risks **silent visual carry-over**: the model partially inherits the wrong jewelry shape, color, or density even when the prompt text says "ignore this image's jewelry." Visual priors override text instructions in image generation.

Only escalate to using a draft as a transient visual anchor when:

- The model/wardrobe/scene/composition in the failed draft is materially better than the Pre baseline, AND
- You cannot describe the missing precision in prompt text alone, AND
- You write a clear `ref_roles` entry stating the failed image's jewelry MUST be treated as transparent/invisible, AND
- You have already tried at least one round with Pre as the anchor.

Even then, prefer crop, prompt rewording, or swapping product refs over feeding failed candidates back as visual input.

If the same issue persists across candidates, change prompt strategy, crop, or refs instead of rerunning blindly. Do not force an image into final just because several candidates have already been generated.

Only candidates that pass the final gate may be promoted into `style/` as persistent anchors, such as `series-anchor`.

Do not use generation-stage labels in prompt metadata, `review.csv`, written review notes, image filenames, or draft folder names. The candidate suffix and review notes are enough for traceability.

## Anti-patterns From Past Sessions

These are concrete failure modes observed while iterating real notes. Each one looks reasonable at decision time but produces predictable bad output.

### 1. Using a failed candidate as the next round's visual anchor

- Symptom: previous candidate failed product fidelity (e.g. "necklace rendered as mini-pearls"); the next round adds the failed candidate to the `ref` array as the model/scene anchor with prompt text saying "ignore the jewelry in Image 1."
- Why it fails: image generation models weight visual priors above text. Even with explicit "ignore" text, the failed jewelry shape, color, and density partially carry over — beads stay too small, opacity stays too high, palette stays off.
- Correct action: keep the **Pre** (`style/style-positioning-anchor.png`) — or, once a product-correct cover exists, the `series-anchor` — as the visual anchor for every formal slot. The Pre is jewelry-free by design; the series-anchor has correct jewelry. Failed candidates belong in `review.csv` notes as written context, not in the `ref` array.

### 2. Choosing a product-ref whose physical form does not match the generation target

- Symptom: necklace product-ref is a top-down photo of the necklace laid out as a flat circle on a backdrop. The cover prompt asks for a half-body shot where the necklace hangs on the collarbone in a natural curve.
- Why it fails: the model has to do a non-trivial transform from "flat ring" to "draped curve on a 3D neck." The transform leaks: bead spacing collapses, bead size shrinks, the curve becomes a tight choker, or the necklace becomes a generic small-bead string.
- Correct action: prefer product refs whose **shape already matches the generation target's drape**. For "hanging on collarbone" generations, choose product refs that show the necklace in a natural wave / hanging from a hand / hanging on a stand / draped diagonally. Top-down flat circles are best reserved for still-life slots (e.g. slot 08 full-set still life), not for body-worn covers.

### 3. Choosing a wearing-ref whose camera angle does not match the generation target

- Symptom: cover composition is 3:4 half-body with a 3/4 turn toward a prop. The wearing-ref in the prompt is a frontal close-up showing the necklace head-on against a chest-up frame.
- Why it fails: the model uses the wearing-ref for proportion (collarbone position, bead-to-neck size, earring drop length). When the wearing-ref's angle differs from the target angle, the proportion math fails: the necklace lands in the wrong arc, the visible bead count is wrong, the earring drop angle is wrong.
- Correct action: pick the wearing-ref whose **camera angle is closest to the target composition**. For a 3/4 half-body cover, prefer a 3/4 worn shot. For a side-profile slot, prefer a side worn shot. For a frontal neckline-zoom slot, the frontal worn shot is right. Always check the worn-shot inventory before defaulting to "the most famous wearing image."

### Combined heuristic

Before generating any complex-product slot, run this 3-question pre-flight on the proposed `ref` array:

1. Is the visual anchor (Image 1) a clean Pre, an accepted series-anchor, or — only with explicit justification — a transient draft?
2. Does each product-ref show the product in a form (drape / angle / scale) close to how it should appear in the generated image?
3. Does the wearing-ref's camera angle match the generation target's composition?

If any answer is "no," fix the `ref` selection before invoking the generation tool. Three failed candidates from a wrong `ref` selection cost more than five minutes spent picking better refs.

## Storage

Save formal candidates directly under the slot folder. Use a continuous two-digit suffix for that slot:

```text
drafts/<slot-id>/<product>_<note>_<slot-id>_01.png
drafts/<slot-id>/<product>_<note>_<slot-id>_02.png
drafts/<slot-id>/<product>_<note>_<slot-id>_03.png
```

Do not create generation-stage folders. The slot id plus suffix is the visible asset identity.

A complex product image cannot enter final if the actual generation did not use product reference images.
