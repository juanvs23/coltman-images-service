# The LoRA catalogue

What a LoRA is, what it costs on this machine, **what each one actually does**,
and where to look for more. Numbers are measured here or read from the Hub;
nothing is estimated unless it says so.

## 1. What a LoRA is, in one page

A LoRA does not replace a model. It is a **patch on the matrices that already
exist**. For a weight `W` of shape `d_out × d_in`, a LoRA stores two narrow
matrices — `A` of `r × d_in` and `B` of `d_out × r`, with `r` between 4 and 64 —
and the adapted weight is

```
W' = W + (α / r) · B·A
```

where `α` is the scaling factor the adapter was trained with. The base weights
stay frozen; the patch is tens or hundreds of megabytes instead of gigabytes,
because it stores **the correction**, not the knowledge. (Hu et al., *LoRA: Low-Rank
Adaptation of Large Language Models*, arXiv:2106.09685, 2021.)

**Two ways to use one, and the difference is the whole cost story:**

- **Merged.** `W'` is computed once and written over `W`. No extra memory and, in
  the paper's words, *no additional inference latency*. But the adapter is baked
  in: changing the set means merging again.
- **Unmerged.** `A` and `B` stay separate and are applied on every forward pass.
  Costs memory equal to the patch and time per step, and is the only way to swap
  adapters without touching the weights.

The vendored runtime exposes both as `--lora-apply-mode immediately` and
`at_runtime`. On a **quantised** model it chooses `at_runtime` by itself, and its
own help warns that merging into quantised weights *"may have precision and
compatibility issues"*. Merging has not been measured here — see §8.

**One LoRA is one concept.** A style, a face, an object, a capability. There is no
universal LoRA, and two or three can be combined with weights
(`add_weighted_adapter` in PEFT is the reference implementation of exactly this).

**ControlNet is not a LoRA.** A LoRA changes *what* is drawn; ControlNet changes
*where* — pose, depth, edges.

## 2. What it costs on this card

Measured 2026-11-17, RTX 4060 Laptop, 7857 MiB torch-usable, 512×512, eight steps,
one 325 MB LoRA duplicated by hardlink to obtain distinct paths:

| LoRAs at once | Wall | Device peak |
| --- | --- | --- |
| 0 | 7.3 s | 3273 MiB |
| 1 | 8.5 s | 4063 MiB |
| 2 | 10.1 s | 4377 MiB |
| 3 | 11.7 s | 4689 MiB |
| 8 | 19.2 s | 6251 MiB |
| 11 | 23.6 s | 7189 MiB |
| 12 | 39.9 s | 7589 MiB |
| 16 | 51.0 s | 7601 MiB |

Three facts, and the third is the one that shaped this document:

1. **The first LoRA carries a fixed cost** of roughly 476 MiB — the machinery, not
   the weights.
2. **After that the cost follows the bytes**: +313 MiB for a 310 MiB file, about
   one to one. A 76 MB LoRA costs about a quarter of a 325 MB one. This is
   theoretical in §1 and observed here, and it is why the system counts **MiB and
   not units**.
3. **From twelve the memory stops growing and the time doubles.** 23.6 s at
   eleven, 39.9 s at twelve, 51.0 s at sixteen — with **no out-of-memory failure
   anywhere up to sixteen**. The limit is throughput, not survival, so a count
   would have been the wrong thing to encode.

## 3. The rules this project adopted

- **A model owns its LoRAs.** Files live at
  `model/assets/loras/<entry-id>/<alias>.safetensors`, and a catalogue path
  outside that folder is refused at boot. Not because a LoRA cannot be reused —
  a patch whose base architecture matches usually works on another checkpoint of
  that architecture — but because **there is no certainty of it**, and a LoRA
  that silently applies nothing is worse than one that is refused. If someone
  verifies a LoRA on a second model, they **copy** the file into that model's
  folder.
- **A LoRA alias is scoped to its entry.** Aliases are not global. `anime` in
  klein's catalogue and `anime` in Z-Image's are two different files, and that is
  normal. Resolution happens against the served entry only, which is unambiguous
  because one model is served at a time.
- **The budget is in MiB.** The host declares how much device memory it dedicates
  to LoRAs and the request is refused when the files' own sizes exceed it — with
  the arithmetic named, not with a count.
- **`sd.cpp` needs a patch to apply a FLUX.2 LoRA at all.** Without
  `patches/0001-flux2-lora-name-conversion.patch` it loads the file, reports
  `apply lora at runtime`, and discards half the tensors as unused while the
  render completes.

## 4. The thing that decides the toolbox: text-to-image or edit

**The request this service accepts carries a prompt, a seed, a size, a step count
and an output path. It carries no image.** Half of the "production tools" in the
klein family are **editing** LoRAs: they expect a picture in, a mask, a highlighted
region or a clothing-agnostic body, and their trigger text says so. Without an
input image they cannot be used, and a catalogue that lists them beside the
text-to-image ones would be a list of wishes.

So the catalogue is split in two, and the split is the honest part of it.

## 5. FLUX.2 [klein] 4B — what each one does

83 LoRAs declare `base_model: black-forest-labs/FLUX.2-klein-4B`. Sizes with a
number were read from the Hub; a dash means the size is read at resolve time with
`stat`.

### 5.1 Works from a prompt alone — usable today

| Alias | What it does | Trigger, in the author's words | Downloads | Size |
| --- | --- | --- | --- | --- |
| `pixel-art` | turns a subject into a pixel-art sprite or game asset, transparent background included | `pixel art sprite, <subject>, game asset, transparent background` | 9 282 | 325 MB |
| `anime` | anime and manga illustration style | **`anime_style`** | 768 | 185 MB |
| `spritesheet` | lays a character out as a sprite sheet for animation frames | `2x2 sprite sheet` | 233 | — |
| `concept-art` | NASA concept-art register — spacecraft, missions, retro-futurism | — | 123 | — |
| `medieval` | marginalia of a medieval manuscript — drolleries, grotesques in the margins | — | 191 | — |
| `mikkoani`, `mikkoph` | two further animation-illustration styles, same subject, different voices | — | 717 / 330 | — |
| `numzoo` | a personal style the author trained | — | 141 | — |
| `curl-v1` | hair curls | — | 103 | — |
| `fastcello` | speed and style, two repos | — | 192 | — |
| `kleinreal` | pushes toward photographic realism; the card documents no trigger | — | 258 | — |
| `flux-wild-africa` (MIT) | African wildlife register | — | 253 | — |
| `Sun-Direction-Lora` | the direction of light in the scene | — | 0 | — |

**The `althjs/sig_*` family — 23 LoRAs, Apache-2.0, text-to-image.** Each is a
**face**: `a_20s_female_korean`, `a`, `b_40s_male_western`, `c_30s_male_eastern`,
`d`, `e_elderly_male`, `f_child_male`, `g_child_female`, `h`, `i`, `j`, `k`, `l`,
`m`, `n`, `o`, `p`, `q`, `r`, `s`, `t_elderly_female_eastern`,
`u_elderly_female_western`, `v_elderly_male_eastern`. Age, gender and region are
the axes; the point is a **recurring character** — the same person across ten
images — without training anything.

### 5.2 Needs an image in — unusable until the request carries one

| Alias | What it does | What it expects | Downloads | Size |
| --- | --- | --- | --- | --- |
| `consistence-edit` | re-renders an edit while keeping the subject consistent and restoring detail | a source image and an edit instruction; the card's pattern is `{instruction}. transform the image to realistic photograph. add realistic details to the corrupted image. restore high frequence details from the corrupted image.` | 2 531 | 385 MB |
| `tryon` | puts a garment on a person | **`TRYON a full-body photo of a person. Replace the outfit with the top and bottom as shown in the reference images. The final image is a full body shot.`** — and the person must go in **clothing-agnostic**, with the outfit region greyed, exactly as it was trained | 894 | — |
| `outpaint` | extends the frame beyond its borders | an image with the new area filled in green: **`Fill the green spaces according to the image`** | 353 | 76 MB |
| `object-remove` | deletes an object | the object highlighted: **`Remove the highlighted object from the scene`** | 274 | — |
| `background-remove` | cuts the background out | an image: **`Remove the background from the image`** | 245 | 76 MB |
| `zoom` | re-frames closer without re-rendering | the target region marked: **`Zoom into the red highlighted area`** | 173 | — |
| `sim-to-real` | turns a synthetic-looking scene into a photograph | a scene: **`Turn this scene into a real photo`** | 238 | — |
| `texture-albedo` | a texture map into an albedo map | a texture | 127 | — |
| `season-winter`, `season-autumn` | turns a summer scene into winter or autumn | a scene | 127 / 122 | — |

### 5.3 Excluded, and why

- **No verifiable licence** — `license: other` in the card: `giannisan`,
  `AnimeOverlord` (mc, mc-v2, mc-v3), `wgruner`, `MarioAlviano` (sofia, dog),
  `saisriteja`, `mariosesan`, `HaaDeej`, `LAXMAYDAY`. No licence tag at all:
  `Vip5200`, `Omnico`, `kphil01`, `NuraStudios`, `cactusfriend`.
- **Not an inference LoRA**: `kigland/flux2_klein_4b_training_adapter` is a
  training adapter; `Emilio407/flux2tiny-MiniCPM5-1B` and `KiwiMate-Image-Mini-1.0`
  are other models wearing a LoRA's name.

## 6. Z-Image Turbo — what each one does

867 LoRAs declare `base_model: Tongyi-MAI/Z-Image-Turbo`; the forty most
downloaded are surveyed here. All of the following are **text-to-image** and
carry a verified licence (Apache-2.0 unless marked).

| Alias | What it does | Trigger | Downloads |
| --- | --- | --- | --- |
| `pixel-art` | pixel-art style | **`Pixel art style.`** | 15 338 |
| `classic-painting` | portraits with the gravitas of the Old Masters; still life with painterly detail | — | 6 379 |
| `realism` | ultra-realistic scenes in a consistent style | — | 5 659 |
| `realistic-snapshot` | snapshot-photograph look | — | 3 756 |
| `portrait` (AWPortrait-Z) | portrait beauty with wider ethnic coverage — the card's aim is to break the "same-face" barrier | — | 3 261 |
| `pixelart-redmond` | a second, heavier pixel-art voice | **`Pixel Art, PixArFK`** | 2 796 |
| `ultrareal` (Lenovo) | ultra-real detail | — | 1 939 |
| `detailed-eyes` | sharper eyes | — | 1 627 |
| `color` (Technically-Color) | classic-film colour | **`t3chnic4lly`** | 1 486 |
| `coloring-book` | line art, colouring-book register | — | 1 399 |
| `icons` | icons and glyphs | — | 865 |
| `anime` (Haruka041) | anime style | — | 848 |
| `sunbleached` (MIT) | sun-bleached film | — | 674 |
| `anime-z` | a second anime voice | — | 613 |
| `mmorpg` | 3D MMORPG art style | — | 580 |
| `grain` (GrainScape) | film grain | — | 522 |
| `historic-color` | period colour palettes | — | 498 |
| `age-slider` | moves an age up or down | — | 496 |

**Excluded**: no verifiable licence — `wcde/Z-Image-Turbo-DeJPEG` (13 608, the most
downloaded non-NSFW of the family, and it declares nothing), `pmczip`,
`DeverStyle`, `wxwhj`, `alexc593`, `JosephMinchala`, `seanjang990` (two),
`harita001`, `wolfer45`, `SaveliiAge`; content this project does not carry — the
NSFW and XXX block, about ten repositories; training, not inference —
`ostris/zimage_turbo_training_adapter` (50 321).

**And the obstacle**: Z-Image runs through **diffusers**, whose adapter has no LoRA
support today. This catalogue is a list of what exists, not of what the service can
serve.

## 7. Filling the toolbox

**klein, text-to-image, all Apache-2.0 — five files, 1,047 MB:**

| Purpose | LoRAs | Why |
| --- | --- | --- |
| a subject as a game sprite | `pixel-art` + `spritesheet` | one makes the sprite, the other lays it out as frames |
| an illustrated register | `anime` (`anime_style`) or `mikkoani` | two voices for the same need; pick one |
| a recurring character | one or two from `sig_*` | the only route to the same face across images today |
| a mood or period | `concept-art`, `medieval` | narrow registers, useful for thumbnails |
| realism | `kleinreal` | unmeasured; the base model is already photoreal |

That is the honest toolbox: **four purposes, five files.** The seven edit tools
become usable the day the request carries an image — and that is a decision about
the service, not about the LoRAs.

**Z-Image, text-to-image — four files, about 680 MB:** `pixel-art` (`Pixel art
style.`), `classic-painting`, `realism`, `portrait`. Blocked on the diffusers half
of the contract.

## 8. What a LoRA is not

Compatibility is decided by **the module tree and the tensor shapes**, not by
family, not by lineage, not by a shared text encoder.

| From → to | Works? | Why |
| --- | --- | --- |
| SDXL → an SDXL fine-tune (DreamShaper, Juggernaut) | usually yes | same modules, same shapes |
| FLUX.1 dev ↔ FLUX.1 schnell | yes | same architecture |
| FLUX.1 → FLUX.2 | no | different modules |
| klein **4B** → klein **9B** | no | different widths |
| klein Q4 → klein fp8 or bf16 | yes | same architecture, only the storage changes |
| Z-Image → klein | no | different architectures |

And the failure mode to fear is not an error. Measured here on 2026-11-17: the
runtime loaded a FLUX.2 LoRA, reported success, discarded 86 of its 172 tensors,
rendered without complaint, and produced a still that differed from the same
prompt without the LoRA by a mean of 4.8 of 255 — nothing at all.

## 9. Where to look for more

**The Hub search, filtered by base model** — the only reliable filter:

```
https://huggingface.co/models?filter=lora&filter=base_model:black-forest-labs/FLUX.2-klein-4B
https://huggingface.co/models?filter=lora&filter=base_model:Tongyi-MAI/Z-Image-Turbo
```

Through the API, which is what this document was built with:

```sh
curl -s "https://huggingface.co/api/models?filter=lora&filter=base_model:<repo-id>&limit=100&sort=downloads&direction=-1"
```

**Before downloading anything, read four things:**

1. `base_model` — it must name **your** checkpoint, not its family.
2. The licence — read the file, not the tag. `license: other` means "read it"; a
   missing `LICENSE` means "you cannot claim it".
3. **The trigger and the example prompts** — they tell you whether it is a
   text-to-image tool or an editing tool, which decides whether this service can
   use it at all.
4. The weights it was trained at — a style LoRA run at 1.0 is not the same tool as
   the same file at 0.5.

**Two traps worth naming.** A repository named after a LoRA may contain a
checkpoint (two of the 83 do). And a training adapter looks exactly like an
inference LoRA until you read what it is for.

## 10. What is not measured

- **Merging** (`--lora-apply-mode immediately`) on a quantised model: not tried. If
  precision holds, the LoRA memory cost falls to zero and the budget becomes
  decorative.
- **Quality interference above three LoRAs.** Three stack without visible damage on
  one prompt and one seed; where two styles begin to fight is not measured.
- **The plateau's cause.** From twelve LoRAs the runtime stops growing in device
  memory and doubles its wall time; that it is moving adapter tensors to system
  memory is a plausible reading, not an observation.
- **Every "what it does" in §5 and §6 is the author's claim.** "Consistent
  character", "virtual try-on", "sharper eyes" are what the card says the file
  does. None has been rendered here, and this project does not repeat a claim as
  its own until it has seen the still.
- **Whether the edit half is worth the plumbing.** Seven of klein's tools need an
  image in, and the request cannot carry one. That is a decision about the service,
  not a measurement.
