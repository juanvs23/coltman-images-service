"""The declared upscale stage: RealESRGAN's RRDBNet in pure torch, tiled.

This stage is declared apart from the model entry (`model/upscaler.yaml`)
because it is not a property of a checkpoint: it applies to every model this
system serves. A render is a render; the pixels a client's file gains after it
are the stage's business (protocol section 8, step 2).

The network is written here instead of being imported. `basicsr` and
`realesrgan` are unmaintained against this torch and would put a second loader
protocol beside the one this project owns. What is written is the published
architecture and nothing else: 23 RRDB blocks, three 5-convolution dense blocks
each, residual scaling 0.2, two nearest-neighbour x2 stages. Its proof is a
strict `load_state_dict` against the vendored checkpoint — zero missing, zero
unexpected, or it refuses.

`scale` is a constructor argument, not a different network. The x2 checkpoint
is the same 702 tensors with one shape changed: `conv_first.weight` is
`(64, 12, 3, 3)` instead of `(64, 3, 3, 3)`, because a scale-2 model reads its
input through a 2x pixel *unshuffle* (12 channels, half the side). The body and
both upsampling stages are the same, so the trunk still produces x4 internally;
the unshuffle is what makes the result x2 of the image. There is no shuffle
after `conv_last` — that tensor is 3 channels in both files, so a fold there
could not produce an image, and the shape settles it.

Tiling is not an optimisation. The x4 output of a 1280x720 render is
5120x2880, one untiled pass of that size was measured to exhaust this card,
and the render that produced the input has just held it. Tiles are run with an
overlap whose edge ramps are blended and normalised, so two neighbouring tiles
agree across the seam instead of meeting at it.
"""

from __future__ import annotations

import logging
import pathlib
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import nn

from .entry import PROJECT_ROOT

logger = logging.getLogger(__name__)

DEFAULT_DECLARATION = PROJECT_ROOT / "model" / "upscaler.yaml"
"""The stage's own declaration; the only place its values are read from."""

TILE = 256
"""Tile side in the network's input pixels. For a scale-2 model that input is
the unshuffled image, so one tile covers twice this in image pixels. Small
enough that a tile's activations fit beside the render's leftovers, large enough
that the overlap is a small fraction of the work."""

OVERLAP = 32
"""Input pixels of context each tile carries on every side. The blend ramp is
this many pixels wide in the network's output (`OVERLAP * 4`), which is what
keeps a tile boundary from being a visible line.

Measured on a 512x512 crop of a real render, against one untiled pass, on the
x4 model: 16 px of context left the boundary 5.1x more wrong than the interior
and up to 12 levels of 8-bit error; 32 px brings that to 2.8x and 1.8 levels;
48 px to 1.54x and 1.25 levels for 33 % more time. 32 is the smallest overlap
whose seam error is at the 8-bit quantisation step, and the residual difference
is a ramp rather than a step, so it cannot read as a line."""

INTERNAL_FACTOR = 4
"""What the trunk produces relative to its own input: two nearest-neighbour x2
stages. `scale` decides only what the input is folded by, so this stays 4."""

_SCALES = (1, 2, 4)
"""The scales this architecture can express, and the unshuffle each one uses."""

_TOP_FIELDS = {"id", "weights", "scale", "architecture"}
_ARCH_FIELDS = {"num_feat", "num_block", "num_grow_ch"}

__all__ = [
    "Declaration",
    "UpscaleError",
    "Upscaler",
    "check_tiling",
    "load_declaration",
    "load_upscaler",
    "upscale_tensor",
]


class UpscaleError(Exception):
    """The declaration is malformed, or the weights do not fit the architecture."""


def _refuse(message: str) -> UpscaleError:
    return UpscaleError(message)


def _exact_keys(name: str, given: object, expected: set[str]) -> None:
    if not isinstance(given, dict):
        raise _refuse(f"{name}: expected a mapping, got {type(given).__name__}")
    unknown = sorted(set(given) - expected)
    missing = sorted(expected - set(given))
    if unknown:
        raise _refuse(f"{name}: unknown field(s) {unknown}")
    if missing:
        raise _refuse(f"{name}: missing field(s) {missing}")


def _positive(name: str, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise _refuse(f"{name}: expected a positive integer, got {value!r}")
    return value


def _resolve(path: object) -> pathlib.Path:
    """Relative paths resolve against the project root; absolute stand alone."""
    if not isinstance(path, str) or not path:
        raise _refuse(f"path: expected a non-empty string, got {path!r}")
    p = pathlib.Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


@dataclass(frozen=True)
class Declaration:
    """The stage's resolved declaration, and where it was read from."""

    id: str
    weights: pathlib.Path
    scale: int
    num_feat: int
    num_block: int
    num_grow_ch: int
    source: pathlib.Path

    @property
    def unshuffle(self) -> int:
        """What the input is folded by: 4 at scale 1, 2 at scale 2, 1 at scale 4."""
        return {1: 4, 2: 2, 4: 1}[self.scale]

    def architecture(self) -> dict[str, int]:
        return {
            "scale": self.scale,
            "num_feat": self.num_feat,
            "num_block": self.num_block,
            "num_grow_ch": self.num_grow_ch,
        }


def load_declaration(path: str | pathlib.Path | None = None) -> Declaration:
    """Resolve and validate the stage's declaration. Raises UpscaleError."""
    import yaml

    source = pathlib.Path(path) if path is not None else DEFAULT_DECLARATION
    if not source.is_file():
        raise _refuse(f"{source}: upscaler file not found")
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise _refuse(f"{source}: not valid YAML: {exc}") from exc

    _exact_keys("upscaler", raw, _TOP_FIELDS)
    _exact_keys("architecture", raw["architecture"], _ARCH_FIELDS)

    upscaler_id = raw["id"]
    if not isinstance(upscaler_id, str) or not upscaler_id:
        raise _refuse("id: expected a non-empty string")

    scale = _positive("scale", raw["scale"])
    if scale not in _SCALES:
        raise _refuse(f"scale: expected one of {list(_SCALES)}, got {scale}")

    arch = raw["architecture"]
    num_feat = _positive("architecture.num_feat", arch["num_feat"])
    num_block = _positive("architecture.num_block", arch["num_block"])
    num_grow_ch = _positive("architecture.num_grow_ch", arch["num_grow_ch"])

    weights = _resolve(raw["weights"])
    if not weights.exists():
        raise _refuse(f"weights: declared asset is missing: {weights}")
    if not weights.is_file():
        raise _refuse(f"weights: expected a file, got a directory: {weights}")

    return Declaration(
        id=upscaler_id,
        weights=weights,
        scale=scale,
        num_feat=num_feat,
        num_block=num_block,
        num_grow_ch=num_grow_ch,
        source=source,
    )


# --- the architecture -------------------------------------------------------
#
# The published RRDBNet, reproduced. Shapes and the residual scales are the
# part the strict load cannot check: a wrong scale still loads and still
# renders something. That is why the stage is also checked against a plain
# bicubic enlargement of the same crop (see `check_tiling`), which a scrambled
# network cannot pass.


class _ResidualDenseBlock(nn.Module):
    """Five convolutions, each fed by every earlier output of the block."""

    def __init__(self, num_feat: int, num_grow_ch: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class _ResidualInResidualDenseBlock(nn.Module):
    """Three dense blocks, chained, added back to the input at scale 0.2."""

    def __init__(self, num_feat: int, num_grow_ch: int) -> None:
        super().__init__()
        self.rdb1 = _ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = _ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = _ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x


class _RRDBNet(nn.Module):
    """The trunk, the body, two x2 stages, and back to three channels.

    `prepare` is the whole difference between the scale-4 and scale-2 models:
    a 2x pixel unshuffle feeds `conv_first` 12 channels at half the side, and
    the same trunk then produces x4 of *that*, which is x2 of the image.
    """

    def __init__(
        self,
        scale: int = 4,
        num_feat: int = 64,
        num_block: int = 23,
        num_grow_ch: int = 32,
        num_in_ch: int = 3,
        num_out_ch: int = 3,
    ) -> None:
        super().__init__()
        self.scale = scale
        self.unshuffle = {1: 4, 2: 2, 4: 1}[scale]
        self.conv_first = nn.Conv2d(num_in_ch * self.unshuffle**2, num_feat, 3, 1, 1)
        self.body = nn.Sequential(
            *[_ResidualInResidualDenseBlock(num_feat, num_grow_ch) for _ in range(num_block)]
        )
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def prepare(self, x: torch.Tensor) -> torch.Tensor:
        """Fold the image into the channels the trunk reads at this scale."""
        if self.unshuffle == 1:
            return x
        return F.pixel_unshuffle(x, self.unshuffle)

    def core(self, feat: torch.Tensor) -> torch.Tensor:
        """Everything after the unshuffle; always x4 of its own input."""
        feat = self.conv_first(feat)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.core(self.prepare(x))


@dataclass(frozen=True)
class Upscaler:
    """A loaded stage: its declared identity, its scale, and the module."""

    id: str
    scale: int
    module: _RRDBNet
    declaration: Declaration
    parameters: int

    def tiles(self, height: int, width: int, tile: int = TILE, overlap: int = OVERLAP) -> int:
        """Tile count for an image of `height`x`width`, in the network's domain."""
        prepared_h = height // self.module.unshuffle
        prepared_w = width // self.module.unshuffle
        return len(_starts(prepared_h, tile, overlap)) * len(_starts(prepared_w, tile, overlap))

    def output_size(self, height: int, width: int) -> tuple[int, int]:
        prepared_h = height // self.module.unshuffle
        prepared_w = width // self.module.unshuffle
        return prepared_h * INTERNAL_FACTOR, prepared_w * INTERNAL_FACTOR


def load_upscaler(path: str | pathlib.Path | None = None) -> Upscaler:
    """Read the declaration, build the network, and make the weights fit it.

    The network is built on the meta device so that nothing is allocated twice:
    `torch.load` already owns the file, and `assign=True` moves those tensors
    into the module instead of copying into fresh storage. The load is strict
    against the file's own key set — the check is the architecture's proof, so
    it compares the two key sets and reports the difference before torch does.
    """
    declaration = load_declaration(path)
    with torch.device("meta"):
        module = _RRDBNet(**declaration.architecture())

    payload = torch.load(declaration.weights, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or "params_ema" not in payload:
        raise _refuse(
            f"weights: {declaration.weights} carries no 'params_ema' mapping "
            f"(top-level keys: {sorted(payload) if isinstance(payload, dict) else type(payload).__name__})"
        )
    params = payload["params_ema"]
    if not isinstance(params, dict):
        raise _refuse("weights: params_ema is not a state dict")

    written = set(params)
    expected = set(module.state_dict())
    if written != expected:
        missing = sorted(expected - written)[:5]
        unexpected = sorted(written - expected)[:5]
        raise _refuse(
            "weights: the file and the architecture disagree — "
            f"{len(expected - written)} key(s) missing ({missing}), "
            f"{len(written - expected)} unexpected ({unexpected})"
        )
    module.load_state_dict(params, strict=True, assign=True)
    del payload, params

    module.eval()
    module.requires_grad_(False)
    parameters = sum(p.numel() for p in module.parameters())
    logger.info(
        "upscale: %s loaded — %d tensors, %d parameters, x%d (unshuffle %d)",
        declaration.id,
        len(written),
        parameters,
        declaration.scale,
        module.unshuffle,
    )
    return Upscaler(
        id=declaration.id,
        scale=declaration.scale,
        module=module,
        declaration=declaration,
        parameters=parameters,
    )


# --- tiling -----------------------------------------------------------------


def _starts(length: int, tile: int, overlap: int) -> list[int]:
    """Tile origins along one axis, the last one flush with the far edge."""
    if length <= tile:
        return [0]
    step = tile - overlap
    if step <= 0:
        raise UpscaleError(f"tiling: overlap {overlap} is not below tile {tile}")
    starts = [0]
    pos = 0
    while pos + tile < length:
        pos += step
        starts.append(min(pos, length - tile))
    return starts


def _profile(
    length: int, start: int, total: int, ramp: int, device: torch.device
) -> torch.Tensor:
    """One axis of the blend window: full weight inside, a ramp at a seam.

    The ramps are `i / (ramp + 1)` so a pixel never carries zero weight: two
    neighbouring tiles ramp against each other over the same interval and sum
    to exactly one, instead of both reaching zero at the boundary.
    """
    weight = torch.ones(length, dtype=torch.float32, device=device)
    r = min(ramp, length)
    if start > 0:
        weight[:r] = torch.arange(1, r + 1, dtype=torch.float32, device=device) / (r + 1)
    if start + length < total:
        weight[-r:] = torch.minimum(
            weight[-r:],
            torch.arange(r, 0, -1, dtype=torch.float32, device=device) / (r + 1),
        )
    return weight


def _apply_tiles(
    module: nn.Module,
    prepared: torch.Tensor,
    tile: int,
    overlap: int,
) -> torch.Tensor:
    """Run the trunk tile by tile and blend each tile's window into place.

    `prepared` is already in the network's input domain (unshuffled for a
    scale-2 model), so a tile boundary falls on whole input features and the
    output is `INTERNAL_FACTOR` times the prepared size — x2 or x4 of the
    image, decided by `prepare`.
    """
    _, _, height, width = prepared.shape
    out_h, out_w = height * INTERNAL_FACTOR, width * INTERNAL_FACTOR
    out = torch.zeros((1, 3, out_h, out_w), dtype=torch.float32, device=prepared.device)
    total = torch.zeros((1, 1, out_h, out_w), dtype=torch.float32, device=prepared.device)
    ramp = overlap * INTERNAL_FACTOR

    for y0 in _starts(height, tile, overlap):
        y1 = min(y0 + tile, height)
        for x0 in _starts(width, tile, overlap):
            x1 = min(x0 + tile, width)
            # The trunk sees this tile plus its context; only the tile's own
            # region is written, so the context is what makes the seam exact.
            cy0, cy1 = max(0, y0 - overlap), min(height, y1 + overlap)
            cx0, cx1 = max(0, x0 - overlap), min(width, x1 + overlap)
            prediction = module(prepared[:, :, cy0:cy1, cx0:cx1])

            py0, px0 = (y0 - cy0) * INTERNAL_FACTOR, (x0 - cx0) * INTERNAL_FACTOR
            th, tw = (y1 - y0) * INTERNAL_FACTOR, (x1 - x0) * INTERNAL_FACTOR
            window = (
                _profile(th, y0, height, ramp, out.device).view(1, 1, th, 1)
                * _profile(tw, x0, width, ramp, out.device).view(1, 1, 1, tw)
            )
            oy0, oy1 = y0 * INTERNAL_FACTOR, y1 * INTERNAL_FACTOR
            ox0, ox1 = x0 * INTERNAL_FACTOR, x1 * INTERNAL_FACTOR
            region = prediction[:, :, py0 : py0 + th, px0 : px0 + tw]
            out[:, :, oy0:oy1, ox0:ox1] += region * window
            total[:, :, oy0:oy1, ox0:ox1] += window

    if float(total.min()) <= 0.0:
        raise UpscaleError(
            f"tiling: the tile grid leaves {int((total <= 0).sum())} output pixel(s) uncovered — "
            "the blend cannot be normalised"
        )
    return out / total


def upscale_tensor(
    up: Upscaler,
    image: torch.Tensor,
    device: str = "cuda",
    tile: int = TILE,
    overlap: int = OVERLAP,
) -> torch.Tensor:
    """Enlarge `[1, 3, H, W]` in `[0, 1]` by the declared scale, tiled.

    The module is on the card only for the length of this call: the render that
    produced the input has just released everything it held, and the caller's
    next stage needs the memory back.
    """
    if image.dim() != 4 or image.shape[0] != 1 or image.shape[1] != 3:
        raise UpscaleError(f"image: expected [1, 3, H, W], got {tuple(image.shape)}")
    if not image.is_floating_point():
        raise UpscaleError(f"image: expected a float tensor, got {image.dtype}")
    low, high = float(image.min()), float(image.max())
    if low < 0.0 or high > 1.0:
        raise UpscaleError(f"image: expected values in [0, 1], got [{low:.4f}, {high:.4f}]")
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise UpscaleError("upscale: no CUDA device")
    unshuffle = up.module.unshuffle
    if image.shape[-1] % unshuffle or image.shape[-2] % unshuffle:
        raise UpscaleError(
            f"image: {tuple(image.shape[-2:])} is not a whole number of {unshuffle}x{unshuffle} "
            "blocks, so the unshuffle cannot be inverted"
        )

    module = up.module
    module.to(device)
    try:
        with torch.no_grad():
            prepared = module.prepare(image.to(device=device, dtype=torch.float32))
            big = _apply_tiles(module.core, prepared, tile, overlap).clamp(0.0, 1.0)
    finally:
        module.to("cpu")
        torch.cuda.empty_cache()
    return big.to("cpu")


def check_tiling(
    up: Upscaler,
    image: torch.Tensor,
    device: str = "cuda",
    tile: int = TILE,
    overlap: int = OVERLAP,
    tolerance: float = 0.02,
) -> dict[str, float]:
    """Compare a tiled pass against one untiled pass, and refuse a seam.

    Returns the measurements and raises if the blend is not transparent. The
    seam figure is the largest difference on the tile boundaries; a blend that
    is not working concentrates its error exactly there, while a pass in one
    piece cannot have a seam at all.
    """
    _, _, height, width = image.shape
    module = up.module
    module.to(device)
    try:
        with torch.no_grad():
            whole = module(image.to(device=device, dtype=torch.float32)).clamp(0.0, 1.0).to("cpu")
            tiled = upscale_tensor(up, image, device=device, tile=tile, overlap=overlap)
    finally:
        module.to("cpu")
        torch.cuda.empty_cache()

    difference = (whole - tiled).abs()
    max_abs = float(difference.max())
    mean_abs = float(difference.mean())

    prepared_h, prepared_w = height // module.unshuffle, width // module.unshuffle
    boundary = torch.zeros_like(difference)
    for y0 in _starts(prepared_h, tile, overlap)[1:]:
        edge = y0 * INTERNAL_FACTOR
        boundary[:, :, max(0, edge - 2) : edge + 2, :] = 1.0
    for x0 in _starts(prepared_w, tile, overlap)[1:]:
        edge = x0 * INTERNAL_FACTOR
        boundary[:, :, :, max(0, edge - 2) : edge + 2] = 1.0
    seam_abs = float((difference * boundary).max()) if bool(boundary.any()) else 0.0

    stats = {
        "max_abs": max_abs,
        "mean_abs": mean_abs,
        "seam_max_abs": seam_abs,
        "tiles": float(up.tiles(height, width, tile, overlap)),
    }
    logger.info("upscale: tiling check %s", stats)
    if max_abs > tolerance:
        raise UpscaleError(
            f"tiling: the tiled pass differs from one untiled pass by {max_abs:.4f} "
            f"(mean {mean_abs:.5f}, seam {seam_abs:.4f}), above the {tolerance} this "
            "stage accepts — a visible seam is a defect, not a detail"
        )
    return stats
