"""The Float8 linear layer: a drop-in replacement for `nn.Linear`.

The checkpoint stores every quantized projection as an FP8 weight (`qdata`,
`F8_E4M3`, shape `[out, in]`) with one float32 scale per output row
(`_weight_scale`, shape `[out, 1]`). This module keeps those two tensors exactly
as they are and multiplies with `torch._scaled_mm`, so the weights are never
dequantized to bfloat16 and never re-quantized (protocol section 6.2).

The activation side is quantized per row at every call. Its scale is floored at
`1e-12`: an all-zero activation row would otherwise divide by zero and produce
a zero scale (protocol section 6.2, `docs/reference/upstream/`).

`state_dict` keys are `weight`, `weight_scale` and `bias`, so a layer built here
replaces an `nn.Linear` in place. `weight_scale` is a buffer, not a parameter:
it is checkpoint data, not a trained value, and the census counts parameters.
"""

from __future__ import annotations

import torch
from torch import nn

WEIGHT_DTYPE = torch.float8_e4m3fn
"""The stored weight dtype — `F8_E4M3` in the checkpoint."""

EP8_MAX = 448.0
"""The largest finite value of `float8_e4m3fn`."""

SCALE_FLOOR = 1e-12
"""The activation-scale floor. An all-zero row must not yield a zero scale."""

SCALE_DTYPE = torch.float32
"""`torch._scaled_mm` requires float32 scales."""

OUTPUT_DTYPE = torch.bfloat16
"""The product is accumulated into bfloat16."""

_ACCEPTED_DTYPES = (torch.bfloat16, torch.float16, torch.float32)


class F8Linear(nn.Module):
    """A linear layer whose weight lives in FP8 and whose scale is per-row.

    `forward` requires a CUDA tensor: `torch._scaled_mm` has no CPU kernel.
    """

    def __init__(self, out_features: int, in_features: int, bias: bool = False) -> None:
        super().__init__()
        if out_features <= 0 or in_features <= 0:
            raise ValueError(
                f"F8Linear: expected positive sizes, got {out_features}x{in_features}"
            )
        self.in_features = int(in_features)
        self.out_features = int(out_features)
        self.weight = nn.Parameter(
            torch.empty(self.out_features, self.in_features, dtype=WEIGHT_DTYPE),
            requires_grad=False,
        )
        # [out, 1] is the checkpoint's layout; forward transposes it for `scale_b`.
        self.register_buffer(
            "weight_scale",
            torch.ones(self.out_features, 1, dtype=SCALE_DTYPE),
            persistent=True,
        )
        if bias:
            self.bias = nn.Parameter(
                torch.empty(self.out_features, dtype=OUTPUT_DTYPE), requires_grad=False
            )
        else:
            self.register_parameter("bias", None)

    @classmethod
    def from_checkpoint(
        cls,
        qdata: torch.Tensor,
        scale: torch.Tensor,
        bias: torch.Tensor | None = None,
    ) -> F8Linear:
        """Build a layer straight from the file's `qdata` and `_weight_scale`.

        No dequantization happens here: the float8 weight is stored as it was
        read, and the scale keeps its `[out, 1]` shape.
        """
        if qdata.dim() != 2:
            raise ValueError(f"qdata: expected a 2D tensor, got shape {tuple(qdata.shape)}")
        if qdata.dtype != WEIGHT_DTYPE:
            raise ValueError(f"qdata: expected {WEIGHT_DTYPE}, got {qdata.dtype}")
        out_features, in_features = qdata.shape

        flat_scale = scale.reshape(-1) if scale.dim() > 0 else scale
        if flat_scale.numel() != out_features:
            raise ValueError(
                f"weight_scale: expected {out_features} values for {out_features} rows, "
                f"got shape {tuple(scale.shape)}"
            )
        if bias is not None and bias.numel() != out_features:
            raise ValueError(
                f"bias: expected {out_features} values, got shape {tuple(bias.shape)}"
            )

        layer = cls(out_features, in_features, bias=bias is not None)
        layer.weight.data = qdata.detach().contiguous()
        layer.weight_scale = (
            flat_scale.detach().to(SCALE_DTYPE).reshape(out_features, 1).contiguous()
        )
        if bias is not None:
            layer.bias.data = bias.detach().to(OUTPUT_DTYPE).contiguous()
        return layer

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if not x.is_cuda:
            raise RuntimeError(
                "F8Linear: input must be a CUDA tensor — torch._scaled_mm has no CPU kernel "
                f"(got a tensor on {x.device})"
            )
        if x.dtype not in _ACCEPTED_DTYPES:
            raise TypeError(
                f"F8Linear: expected one of {[str(d) for d in _ACCEPTED_DTYPES]}, got {x.dtype}"
            )
        if x.shape[-1] != self.in_features:
            raise ValueError(
                f"F8Linear: expected last dimension {self.in_features}, got {x.shape[-1]}"
            )

        lead = x.shape[:-1]
        rows = x.reshape(-1, self.in_features)

        # Per-row dynamic activation scale, floored so a zero row stays finite.
        scale_a = (
            rows.abs().amax(dim=-1, keepdim=True).float().clamp_min(SCALE_FLOOR) / EP8_MAX
        ).contiguous()
        x_q = (rows.float() / scale_a).to(WEIGHT_DTYPE)

        out = torch._scaled_mm(
            x_q,
            self.weight.t(),
            scale_a=scale_a,
            scale_b=self.weight_scale.t().contiguous(),
            out_dtype=OUTPUT_DTYPE,
        )
        if self.bias is not None:
            out = out + self.bias
        return out.reshape(*lead, self.out_features)

    def extra_repr(self) -> str:
        return (
            f"in_features={self.in_features}, out_features={self.out_features}, "
            f"bias={self.bias is not None}, dtype={WEIGHT_DTYPE}"
        )
