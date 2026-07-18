# Note Assets

Use this reference before creating note assets or prompt refs.

## Note Skeleton

Create the note with:

```bash
python3 scripts/new_note.py <product> <note-name>
```

Then create or confirm:

- `research/`
- `style/xhs-ref-candidates/`
- `style/pre-candidates/`
- `drafts/<slot-id>/`

Do not create generation-stage draft folders. Multi-slot work should use slot-level folders only, with continuous candidate suffixes inside each slot folder.

## Asset Policy

- Image/video binaries stay local and must not be committed to Git.
- Upload repository images to R2 before using them in Markdown.
- Markdown uses R2 public URLs, not local image paths.
- Prompt JSON `ref` entries use local paths because generation tools read local files.
- Use the repo-relative image path as the R2 object key.

If new binary types appear, make sure `.gitignore` keeps them out of Git.

## Reference Roles

Use narrow, single-purpose reference roles:

- `face`: face shape and skin texture only
- `style-ref`: mood, lighting, outfit, scene direction
- `wearing-ref`: wearing proportion only
- `product-ref`: product fidelity only
- `style-positioning-anchor`: accepted Pre image for model direction, outfit language, lighting, scene mood, color temperature, and framing density only
- `series-anchor`: only after a product-correct final cover exists

Do not cite `shared/` files directly from prompt JSON. Copy selected shared/R2 references into note-local `style/` first and record them in `style/_ref-map.md`.

Generated formal candidates have a stricter promotion rule:

- Copy a generated formal candidate into top-level `style/` only after it is judged eligible for `final`.
- Do not copy `shortlist`, `shortlist-anchor`, local-fix anchors, failed product-fidelity attempts, or other non-final candidates into `style/`.
- Keep non-final generated candidates in `drafts/<slot-id>/` and document their use in `review.csv`.
- If a non-final candidate is useful for the next generation, load it visually from `drafts/` during the current session and describe its limited role in prompt text; do not record it as a persistent `style/` reference.

## Product Refs

For every visible product component, include a real product reference:

- visible necklace -> necklace product and/or wearing refs
- visible earrings -> earring product and/or wearing refs
- visible bracelet -> bracelet product and/or wearing refs
- visible packaging/gift/still life -> matching still/product refs

Product structure, color, material, component count, and wearing proportion come from product refs, not text memory.
