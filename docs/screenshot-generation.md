# Screenshot Generation

video-review treats screenshots as versioned batches.

Each video can have multiple screenshot batches:
- batch id
- strategy
- timestamps
- image paths
- created time
- selected/current flag

V1 strategies planned:

1. Uniform default
   - 10%, 25%, 50%, 75%, 90%

2. Intro/outro-safe uniform
   - avoid early intro and final credits

3. Random
   - random N timestamps between configured percentage bounds

4. Manual timestamps
   - user provides exact timestamps such as `00:05:00,00:12:30`

Review UI requirements:
- regenerate one video
- regenerate current filter batch later
- switch historical batches
- mark one batch as current
- deleting screenshot cache must never touch original videos
