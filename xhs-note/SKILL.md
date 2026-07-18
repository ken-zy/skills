---
name: xhs-note
description: Use this skill whenever the user wants to create, plan, generate, review, or iterate Xiaohongshu-style ecommerce product image notes. This includes product image generation, Xiaohongshu high-performing-structure research, note slot planning, Pre style-positioning images, per-slot candidate iteration, review scoring, and finalization. In ecommerce image workspaces, always use this skill before deciding image slots; do not hard-code a generic 9-image plan before market exploration.
---

# XHS Note

This skill helps an AI agent create ecommerce product image notes for Xiaohongshu-style publishing.

When working in the product image repository, communicate user-facing content in Chinese and keep agent-facing files/instructions in English.

## Reference Files

Read these references as the workflow reaches each stage:

- `references/xiaohongshu-research.md`: required before choosing slots. Covers search, candidate download, validation, evidence recording, and style-library fallback.
- `references/note-assets.md`: required before creating note assets or prompt refs. Covers note skeletons, R2/local asset rules, style roles, and Git hygiene.
- `references/prompt-candidates.md`: required before writing Pre/formal prompts or generating images. Also defines the **Generation Tool Routing** rule — Codex agents call `$imagegen` directly after `view_image` of refs in order; Claude Code agents must `Read` every `ref` image in the prompt JSON's exact order, then invoke `/ask-codex` for generation. Also defines **Anti-patterns From Past Sessions** — never feed failed candidates back as visual anchor (use Pre/series-anchor instead), pick product-refs whose drape matches the target, pick wearing-refs whose camera angle matches the target.
- `references/review-scoring.md`: required before scoring drafts, selecting finals, or claiming a note is complete.

## Core Principle

Do not begin by inventing a fixed 9-image layout. The repository requires each active note to reach at least 9 final images before publishing, but the slot structure must come from market exploration first:

1. Study the product and repository rules.
2. Audit existing notes for the product and choose a non-duplicative current theme.
3. Use the chosen theme to define focused Xiaohongshu search targets.
4. Explore and download useful Xiaohongshu examples for this product/style niche.
5. Extract reusable post structures and image archetypes.
6. Map those archetypes to the current product's assets and constraints.
7. Generate one independent `Pre` style-positioning image.
8. Use the accepted `Pre` image as the baseline for formal per-slot candidate generation.
9. Fill gaps with product-specific fallback shots only when market examples and product requirements do not cover the need.

## Required Read Order In The Repo

If the current workspace contains these files, read them before planning:

1. `AGENTS.md`
2. `docs/workflow.md`
3. `docs/handbook.md`
4. `products/<product>/docs/positioning.md`
5. `products/<product>/docs/visual-analysis.md`
6. `products/<product>/docs/priorities.md`
7. `products/<product>/product-assets/index.md`

Treat `docs/workflow.md` and `docs/handbook.md` as the current operating truth. Treat `docs/superpowers/` as archive/reference only.

## Workflow

### Phase 1: Identify Product And Theme

Determine the active product from the user's wording or the local `products/` directory. If only one product exists, use it and state the assumption briefly.

Collect:

- product slug and product category
- available product asset groups
- current active/legacy note directories
- existing note themes and style directions from `products/<product>/notes/*/brief.md`
- product positioning, main style line, secondary style lines, and forbidden directions
- required product fidelity references for each visible component
- the proposed current note theme, explicitly checked against existing notes for overlap
- focused Xiaohongshu search targets derived from the selected theme

For complex products, preserve the rule that product details come from real product refs, not from text memory.

Do not enter Xiaohongshu research until a current note theme has been selected. The theme must come from both product positioning and existing-note gap analysis, not from product positioning alone. If a proposed theme overlaps an existing note, withdraw it and propose a distinct angle before searching.

Use this format when reporting the theme decision:

```markdown
## 已有主题盘点
| 笔记 | 已有主题 | 已有风格/场景 | 本次是否避开 |

## 本次主题
- 主题：
- 与旧主题的差异：
- 小红书搜索目标：
```

### Phase 2: Xiaohongshu Research

Before deciding slots, read `references/xiaohongshu-research.md` and run focused Xiaohongshu exploration unless the user explicitly asks to skip it. The query set must be derived from the selected current note theme, not from a generic product/category search.

Required outputs:

- useful sources with stable ids such as `XHS-01`
- downloaded eligible candidates under `notes/<note>/style/xhs-ref-candidates/<source-id>/`, or a recorded reason why none could be downloaded
- an explicit search-attempt matrix in `research/xhs-structure.md` when no eligible candidate is found; do not stop after one or two weak searches
- source records with engagement, niche match, slide count, model-image count, cover type, first 3 slide sequence, recurring shot archetypes, product proof shots, and mismatch risks
- `notes/<note>/research/xhs-structure.md`

Market-derived sources must have more than 5 model images. Count only images where a visible person, face, upper body, hand, wrist, ear, neck, or other human wearing context is used to show styling or product relation. Do not count pure still life, product-only shots, flowers, scenery, text diagrams, or infographic grids as model images. Candidates with 5 or fewer model images can be recorded as weak signals, product-proof inspiration, or skipped, but they must not be promoted as primary `market-derived` structure evidence.

If the first Xiaohongshu searches do not find an eligible source, continue trying before fallback:

- expand from the initial 3-6 focused queries into a retry matrix that changes at least three axes: scene, product component, style synonym, buyer scenario, and content format
- include component-level searches such as necklace close-up, earring side face, bracelet hand context, full-set/gift, or outfit neckline when relevant
- try both narrow theme terms and one adjacent but still on-position style term; do not jump to unrelated aesthetics
- inspect and, when useful, download candidates that appear likely to pass the gate; search result links alone are not enough
- record every attempted query, count of useful results, downloaded source ids, and rejection reason in `research/xhs-structure.md`

Only use `shared/model-library/styles/` fallback after eligible Xiaohongshu candidates have been downloaded and validated, or after the retry matrix shows that eligible candidates could not be found/downloaded/validated, or after a hard blocker such as login, rate limits, stale tabs, or access denial is recorded.

### Phase 3: Structure Map

Convert the discovered examples into a structure map before writing prompts.

Use this format in the user-facing plan:

```markdown
## 小红书结构观察
| 来源编号 | 来源/关键词 | 高赞结构 | 可迁移点 | 不适合点 |

## 当前商品映射
| 图位候选 | 来源依据 | 商品目的 | 所需参考图 | 优先级 |
```

Persist the same evidence in `research/xhs-structure.md`.

Classify each candidate shot:

- `market-derived`: supported by observed Xiaohongshu structures
- `style-library-derived`: supported by `shared/model-library/styles/` after live evidence is blocked or insufficient
- `product-required`: needed for purchase confidence even if not common in high-like posts
- `fallback`: used only because market exploration did not provide a suitable structure
- `skip`: tempting but mismatched with the product positioning

Only assign `market-derived` when the supporting Xiaohongshu source passes the model-image requirement above. If a post is high-engagement but has too few model images, label its influence as `weak-signal`, `product-proof`, or `skip` in the research notes, then rely on other eligible sources or style-library fallback for slot structure.

Only after this mapping should you propose the final 9+ slot plan.

### Phase 4: Decide Slots

The note must eventually reach at least 9 final images, but the specific slots are not fixed.

Prioritize:

1. A cover structure supported by Xiaohongshu exploration.
2. The first 3 slides as a coherent hook sequence.
3. Product proof shots for every visible product component.
4. Lifestyle/use-context shots that match product positioning.
5. Detail/static/gift shots only where they support conversion or match observed structure.

For each slot, specify image number, stable slot id, role, source classification, scene/composition intent, visible product components, required refs, and candidate iteration strategy.

### Phase 5: Prepare Assets

Before creating note assets, read `references/note-assets.md`.

Required outputs:

- note skeleton from `python3 scripts/new_note.py <product> <note-name>`
- `research/` for market evidence
- `style/xhs-ref-candidates/` for downloaded Xiaohongshu candidates
- `style/_ref-map.md` for every promoted role reference
- slot-level `drafts/<slot-id>/` with candidate filenames that do not expose generation-stage labels
- prompt refs that are note-local or product-local, never direct `shared/` refs

Only promote images into top-level `style/` after they pass the role gate:

- External/Xiaohongshu/style-library reference images may be copied into `style/` only after they are selected as actual prompt references and recorded in `style/_ref-map.md`.
- Generated formal candidates may be copied into `style/` only after they are judged eligible for `final`. Use them as `series-anchor` or other persistent style anchors only after product fidelity passes the final gate.
- Non-final candidates, including `shortlist`, `shortlist-anchor`, and local-fix anchors, must stay in `drafts/<slot-id>/` and `review.csv`. Do not copy them into `style/`.
- If a non-final candidate is useful for the next generation, load it visually from `drafts/` in the current session and describe its limited role in the prompt text; do not persist it as a `style/` reference.

### Phase 6: Pre Style Positioning

Before formal candidate generation, read `references/prompt-candidates.md` and create one independent `Pre` style-positioning image.

`Pre` is not slot 01 and does not count toward the final 9 images. It only locks model direction, outfit language, lighting, scene mood, color temperature, and framing density. Product fidelity in formal candidates must still come from real product refs.

If `Pre` is labeled `market-derived`, the eligible Xiaohongshu source must be represented by actual selected images in the prompt `ref` list and loaded visual context. Do not use Xiaohongshu research only as a text summary while generating from style-library refs. Style-library refs may supplement the XHS images, but they must not replace the XHS images that justified the `market-derived` label.

Do not start formal slot generation until a Pre baseline is accepted and copied to `style/style-positioning-anchor.png`.

### Phase 7: Formal Candidate Iteration

For each image slot, write or update one prompt JSON under `prompts/`.

Each formal slot follows its own candidate iteration path:

- The first formal candidate includes accepted Pre plus all product refs for visible components.
- Score every candidate before deciding whether another candidate is needed.
- Stop immediately if any candidate reaches the final gate.
- Use follow-up candidates only for named, fixable issues from the prior score.
- Do not use generation-stage labels in prompt JSON, `review.csv`, notes, image filenames, or folder names.
- Do not promote non-final candidates into `style/` as composition/style/product anchors.

Save candidates by slot only, with a continuous two-digit suffix for that slot:

```text
drafts/<slot-id>/<product>_<note>_<slot-id>_01.png
drafts/<slot-id>/<product>_<note>_<slot-id>_02.png
drafts/<slot-id>/<product>_<note>_<slot-id>_03.png
```

### Phase 8: Review And Finalize

Before scoring or finalizing, read `references/review-scoring.md`.

After each formal candidate:

1. Move selected generated images from `$CODEX_HOME/generated_images/` into `drafts/<slot-id>/`.
2. Run `python3 scripts/sync_review_csv.py <note-dir>`.
3. Review and score each draft against the prompt, product refs, and structure-map purpose.
4. Fill `score`, `status`, `final_file`, and `notes` in `review.csv`.
5. Copy, not move, qualified images into `final/`.
6. Only after a candidate is qualified for `final`, optionally copy it into `style/` as a persistent anchor and record it in `style/_ref-map.md`.
7. Continue planning/generating if `final/` has fewer than 9 images.

Before copying any candidate into `final/`, run the full final gate from `references/review-scoring.md`. A candidate does not qualify just because it fixed the last named defect or improved over the previous candidate. Re-open the actual product refs for every visible core component, check whether any hard cap still applies, and write the `review.csv` note as a complete final-gate decision rather than a local improvement note.

Do not call a 3-image validation run a complete note.

## User-Facing Plan Format

When the user asks for a plan, answer in Chinese with this structure:

```markdown
## 我的判断

## 当前逻辑需要优化的点

## 新流程
1. 商品与定位读取
2. 已有笔记主题盘点与去重
3. 本次主题与小红书搜索目标确认
4. 小红书结构探索与候选下载
5. 高赞结构抽象
6. 当前商品映射
7. 图位计划
8. Pre 参考图与 prompt 准备
9. Pre 风格定位图
10. 正式图位 prompt 准备
11. 正式候选图生成与评审
12. 评审与 final

## 下一步
```

When files are changed, list changed paths and verification performed.

## Quality Checks

Before claiming the workflow is ready:

- Confirm the plan does not hard-code a generic 9-slot template.
- Confirm existing note themes were reviewed before choosing the current note theme.
- Confirm the current note theme is meaningfully distinct from prior notes for the same product, or explicitly explain why a repeated theme is intentional.
- Confirm Xiaohongshu search targets come from the selected note theme rather than a generic product search.
- Confirm Xiaohongshu evidence is persisted in `research/xhs-structure.md`.
- Confirm that if the first Xiaohongshu searches found no eligible candidate, the agent continued with a broader retry matrix before using style-library fallback.
- Confirm `research/xhs-structure.md` records the retry matrix: query terms, result quality, downloaded candidates, and rejection/blocker reason.
- Confirm useful Xiaohongshu candidates that pass the date/engagement/content gate were downloaded into `style/xhs-ref-candidates/<source-id>/`, or that `xhs-structure.md` records why no eligible candidate could be downloaded.
- Confirm every source used as primary `market-derived` evidence has more than 5 model images, with the counted model-image total recorded in `research/xhs-structure.md`.
- Confirm sources with 5 or fewer model images are not promoted to primary `market-derived` structure evidence; keep them as weak signals, product-proof references, or skipped candidates.
- Confirm downloaded Xiaohongshu media was inspected and validated before any item was promoted into `style-ref.jpg`, `face.jpg`, or `wearing-ref-*.jpg`.
- Confirm every visually `market-derived` Pre or slot prompt includes selected note-local Xiaohongshu images in `ref`, records them in `style/_ref-map.md`, and loads them as visual inputs before generation.
- Confirm fallback style-library sources are labeled `style-library-derived`, not `market-derived`.
- Confirm every proposed slot has market evidence, product necessity, or explicit fallback status.
- Confirm the workflow has an independent `Pre` style-positioning image before formal slot candidates.
- Confirm every `Pre` candidate is moved into `style/pre-candidates/`.
- Confirm accepted `Pre` is copied to `style/style-positioning-anchor.png`, not counted as slot 01, and not counted toward the final 9.
- Confirm formal prompts use `Pre` only for style/model/light/scene/framing and never for product fidelity.
- Confirm `style/` does not contain generated formal candidates that failed the final gate.
- Confirm non-final candidates remain only in `drafts/<slot-id>/` plus `review.csv`, not in `style/_ref-map.md`.
- Confirm product refs exist for every visible component.
- Confirm prompt refs are note-local or product-local, not direct `shared/` refs.
- Confirm every formal image slot has a stable `slot-id`.
- Confirm drafts are saved directly under `drafts/<slot-id>/`.
- Confirm draft filenames use slot-level continuous suffixes such as `<product>_<note>_<slot-id>_01.png`, without generation-stage labels.
- Confirm the first formal candidate includes product refs for every visible product component.
- Confirm every formal candidate is scored before deciding whether another candidate is needed.
- Confirm follow-up candidates are skipped for any slot that already passes the final gate.
- Confirm the note can still satisfy the minimum 9-final-image rule.
- Run `python3 scripts/validate_repo.py` after file or prompt changes when practical.
