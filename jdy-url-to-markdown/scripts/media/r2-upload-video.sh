#!/usr/bin/env bash
# Upload validated MP4 without conversion. Keep input until caller verifies ALL
# public objects. stdout is exactly one public URL; no source URLs or credentials.
set -eu
set -o pipefail
video_input="${1:-}"
video_key="${2:-}"
video_bucket="${R2_BUCKET:-obsidian-images}"
video_domain="${IMG_SUBDOMAIN:-img.jdy.systems}"
if [[ ! "$video_key" =~ ^web-articles/[a-zA-Z0-9._/-]+/video-[0-9]+$ ]] || [[ "$video_key" == *..* || "$video_key" == *//* || "$video_key" == */./* ]]; then
  echo 'Invalid classified video key' >&2; exit 1
fi
if [[ ! "$video_domain" =~ ^[a-zA-Z0-9.-]+$ || ! -s "$video_input" || ! -f "$video_input" ]]; then
  echo 'Invalid video input or public domain' >&2; exit 1
fi
video_size="$(wc -c < "$video_input" | tr -d ' ')"
if (( video_size > 262144000 )); then
  echo 'MP4 exceeds bundled uploader limit (250 MiB)' >&2; exit 1
fi
command -v ffprobe >/dev/null || { echo 'ffprobe is required' >&2; exit 1; }
video_format="$(ffprobe -v error -protocol_whitelist file,pipe -show_entries format=format_name -of default=nw=1:nk=1 "$video_input" 2>/dev/null)"
video_stream="$(ffprobe -v error -protocol_whitelist file,pipe -select_streams v:0 -show_entries stream=codec_type -of default=nw=1:nk=1 "$video_input" 2>/dev/null)"
if [[ ",$video_format," != *,mp4,* || "$video_stream" != video ]]; then
  echo 'Input is not an MP4 video' >&2; exit 1
fi
# Require an existing Wrangler installation/cache; never install dependencies.
if ! npx --no-install wrangler r2 object put "$video_bucket/$video_key.mp4" --file="$video_input" --content-type=video/mp4 --remote >/dev/null; then
  echo 'R2 video upload failed; input retained' >&2; exit 1
fi
printf 'https://%s/%s.mp4\n' "$video_domain" "$video_key"
