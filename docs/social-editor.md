# Context-First Social Editor

The interesting decision is not “post this to three places.” It is whether a shorter cut changes the meaning, whether more evidence is needed, and whether a clip belongs on a particular account at all.

## The edge-case demo

```bash
python3 -m agentkit social-editor --demo
```

A fictional speaker opens with “Fifteen percent every month. Guaranteed.” The next sentence explains that this is precisely the pitch they would reject. The first proposed cut omits the qualification; the validator flags its explicitly annotated context dependency. The demo expands context and revises the cut. The revised idea fits a research account but fails a travel account's topic policy.

This is a **scripted demonstration with an annotated transcript**, not proof that a model reliably detects sarcasm. In agent mode, the model must infer meaning from the full supplied transcript and available frames; review flags help but do not replace semantic or human review.

## Use a real video

Install FFmpeg/ffprobe from a trusted package source. For optional local speech transcription, install `faster-whisper`; first use downloads its `base` model. This project does not require a hosted transcription subscription.

```bash
python3 -m agentkit.media prepare /path/to/your-video.mp4 \
  --job /path/to/private/job-001 --library /path/to/your-own-footage --transcribe
```

Preparation extracts six sampled frames, mono audio, a timed transcript when requested, and a catalogue of up to 25 local assets. The primary video is sampled; library assets initially have technical metadata and filename hints only. **Semantic search across a whole video library is not implemented in this release.** A person or further vision analysis must assess relevance. There is no claim that six frames capture every important moment.

No full script is required if transcription is available. Review transcription errors and context, especially negation, speaker changes, jokes and quotations. A transcript alone does not establish tone of voice.

Copy and adapt `examples/social-accounts.json` into the job folder. Account limits are your editorial preferences, not hardcoded claims about current social-platform limits. Update rights/privacy/transcript review fields in the manifest only after actually checking them.

```bash
export OLLAMA_VISION_MODEL=YOUR_INSTALLED_VISION_MODEL
python3 -m agentkit social-editor --workspace /path/to/private/job-001 \
  --model YOUR_INSTALLED_TOOL_MODEL \
  --task "Read the clip manifest and account rules. Inspect the sampled images. Propose a story, investigate surrounding context, critique each draft and validate it. If narration is needed, draft a script and ask me to record it. Produce an edit plan using the IDs in assets.json. Do not publish." \
  --output /path/to/private/job-001/agent-review.json
```

Tools include context-window inspection, single-image vision and draft validation. The same bounded model can investigate and revise; there is no claim that an independent second model has approved the result. At most 3 draft revisions per account are requested by the prompt; the runner enforces a hard global 8-turn/16-tool budget.

## Render the proposed edit

Review the model's proposal and save an explicit JSON edit plan:

```json
{
  "canvas": "portrait",
  "clips": [
    {"asset_id": "asset-0", "start": 0, "end": 8, "keep_audio": true},
    {"asset_id": "asset-1", "start": 2, "end": 6, "keep_audio": false},
    {"asset_id": "asset-0", "start": 15, "end": 22, "keep_audio": true}
  ]
}
```

```bash
python3 -m agentkit.media render --job /path/to/private/job-001 \
  --plan /path/to/private/job-001/edit-plan.json \
  --output /path/to/private/job-001/preview-v1.mp4
```

If the story needs voiceover and no approved voice service is configured, the agent drafts a script and asks for a recording. Add `--narration /path/to/your-recording.wav` to replace clip audio with that recording. Narration shorter than the edit is padded with silence; longer narration is trimmed to the edit, so listen to the complete preview. No ElevenLabs connection or cloned voice is assumed.

The renderer validates IDs and time boundaries, checks source hashes, assembles clips, normalizes output to 30fps and saves a hash receipt. The default `fit: "contain"` preserves the whole frame with letterboxing. Use `canvas: "feed"` for 864-by-1080 output and `fit: "cover"` to fill it; `focus_x` and `focus_y` are values from 0 to 1 that position the crop within the available overflow. Inspect the actual frames: these controls do not track faces. An optional `grade: "gym"` adds mild contrast and sharpening without changing body shape.

It supports sequential B-roll inserts, not picture-in-picture overlays, automated face tracking, music sourcing or subtitle generation. The preview limit is 180 seconds. Edit plans are trusted local inputs and should be reviewed; keep job files private. Synced iCloud files may exist as placeholders until opened. Allow them to download, then retry preparation; do not classify a hydration timeout as missing footage.

## Review, revise, publish

1. Inspect the story idea and chosen source clips.
2. Render and watch a complete preview, including sound and transitions.
3. Give feedback; revise the plan/caption and render a new numbered version.
4. Approve the exact final version for the specified account.
5. Publish through an authorized account connection or manually.

**Publishing connectors are not implemented in this prototype.** There are no Instagram, LinkedIn or other social credentials in the repository, and nothing is uploaded automatically. The first real-video pilot must verify transcription, vision, cuts, audio and account-specific output before claiming an end-to-end workflow.
