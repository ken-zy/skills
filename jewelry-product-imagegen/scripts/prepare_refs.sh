#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: prepare_refs.sh <selected-model-image> <product-design-image> <output-root> [product-worn-image]" >&2
  exit 2
fi

MODEL_IMAGE="$1"
PRODUCT_DESIGN_IMAGE="$2"
OUT_ROOT="$3"
PRODUCT_WORN_IMAGE="${4:-}"

if [[ ! -f "$MODEL_IMAGE" ]]; then
  echo "Model image not found: $MODEL_IMAGE" >&2
  exit 1
fi

if [[ ! -f "$PRODUCT_DESIGN_IMAGE" ]]; then
  echo "Product design image not found: $PRODUCT_DESIGN_IMAGE" >&2
  exit 1
fi

if [[ -n "$PRODUCT_WORN_IMAGE" && ! -f "$PRODUCT_WORN_IMAGE" ]]; then
  echo "Product worn image not found: $PRODUCT_WORN_IMAGE" >&2
  exit 1
fi

mkdir -p \
  "$OUT_ROOT/refs" \
  "$OUT_ROOT/half_front_single" \
  "$OUT_ROOT/side_single_closeup" \
  "$OUT_ROOT/front_both_ears" \
  "$OUT_ROOT/final"

sips -s format jpeg -Z 1600 "$MODEL_IMAGE" --out "$OUT_ROOT/refs/selected-model.jpg" >/dev/null
sips -s format jpeg -Z 1600 "$PRODUCT_DESIGN_IMAGE" --out "$OUT_ROOT/refs/product-design.jpg" >/dev/null
cp "$OUT_ROOT/refs/product-design.jpg" "$OUT_ROOT/refs/product-flat.jpg"

if [[ -n "$PRODUCT_WORN_IMAGE" ]]; then
  sips -s format jpeg -Z 1600 "$PRODUCT_WORN_IMAGE" --out "$OUT_ROOT/refs/product-worn.jpg" >/dev/null
fi

echo "$OUT_ROOT/refs/selected-model.jpg"
echo "$OUT_ROOT/refs/product-design.jpg"
if [[ -n "$PRODUCT_WORN_IMAGE" ]]; then
  echo "$OUT_ROOT/refs/product-worn.jpg"
fi
