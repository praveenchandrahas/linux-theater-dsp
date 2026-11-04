# How this differs from EasyEffects and other generic upmixers, and why this route

**What the common tools do, as far as the author knows.**

- **EasyEffects** is a PipeWire effects chain (equaliser, compressor, reverb, and so on). It is built around processing the stereo (or an existing multichannel) stream; it does not make a surround layout out of a stereo one, and it has no notion of ceiling speakers.
- **PipeWire's own upmix** (`channelmix.upmix`, with a `simple` or `psd` method and settings such as `lfe-cutoff` and `rear-delay`) can spread stereo into 5.1 or 7.1. It is a general-purpose, fixed mix for a standard layout, applied inside the sound server before any of your own processing.
- Player and hardware options (ffmpeg's `surround` filter, a receiver's Dolby Surround or DTS Neural:X) are either also fixed matrices for standard layouts or closed.

**What is different here, and why.**

1. **The target is not a standard layout.** The author's rig is 5.1 plus two ceiling speakers (5.1.2) behind a Z906, with different speakers at the front, the sides and the ceiling. Generic upmixers stop at 5.1 or 7.1. `upmix.py` produces 5.1.2: it shares the phantom centre with a real centre speaker, sends only the *side* signal (L minus R, band-limited, decorrelated, delayed 12 to 17 ms) to the surrounds, and feeds the heights from the same ambience, high-passed and delayed more. Mono material (a voice) gives no side signal, so nothing is thrown behind or above you.
2. **It sits in front of the room correction, not instead of it.** The upmix is written as CamillaDSP blocks, so everything after it (per-speaker delays measured with a mic, level trims, bass EQ, bass management for the heights, tone match) works on the result exactly as on a native Atmos feed. A generic upmixer in the sound server cannot know about those, and a room-corrected 8-channel chain cannot be bolted onto an effects plugin without redoing the routing.
3. **It is measurable.** The harness in `tools/upmixtest` scores an upmixer on synthetic signals where the right answer is known (an instrument panned into a mix with reverb): ambience kept in the surrounds minus instrument leaking into them, in dB. That is how the fixed and adaptive versions were compared, rather than by a general sense of "wider".
4. **An adaptive mode exists.** `upmix_engine.py` steers the ambience and ceiling feeds by how correlated the input is, which a fixed matrix (the only thing CamillaDSP can do on its own) cannot. If numpy or scipy is missing, it falls back to the fixed matrix.

**What it does not do, plainly.**

- It is a single-rig, single-seat design. It is not a plugin you drop in, and it has been tuned and measured in one room.
- Its evidence is synthetic signals plus listening, not a blind test on music; the "better than the fixed matrix" result is for the test items and says nothing yet about music in general.
- It does not replace object audio. Real Atmos and DTS:X go through the Omniphony player (`mpv-object-audio`); this project is for stereo and 5.1 sources.
- If you have a plain 5.1 or 7.1 system, PipeWire's built-in upmix or a hardware decoder is simpler and probably enough.

See [Usage](usage.md) for the day-to-day `eq` commands, or [Configuration](configuration.md) to adapt the upmixers and room correction to your own speakers and room.
