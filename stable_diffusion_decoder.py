
from typing import List, Optional, Union

import torch

from diffusers.models import AutoencoderKL
from diffusers.pipeline_utils import DiffusionPipeline
#from .safety_checker import StableDiffusionSafetyChecker


class StableDiffusionDecoder(DiffusionPipeline):
	r"""
	Decoder for text-to-image generation using Stable Diffusion.

	This model inherits from [`DiffusionPipeline`]. Check the superclass documentation for the generic methods the
	library implements for all the pipelines (such as downloading or saving, running on a particular device, etc.)

	Args:
		vae ([`AutoencoderKL`]):
			Variational Auto-Encoder (VAE) Model to encode and decode images to and from latent representations.
	"""

	def __init__(
		self,
		vae: AutoencoderKL,
		#scheduler: Union[DDIMScheduler, PNDMScheduler, LMSDiscreteScheduler],
	):
		super().__init__()
		#scheduler = scheduler.set_format("pt")
		self.register_modules(
			vae=vae,
		)

	def enable_attention_slicing(self, slice_size: Optional[Union[str, int]] = "auto"):
		r"""
		Enable sliced attention computation.

		When this option is enabled, the attention module will split the input tensor in slices, to compute attention
		in several steps. This is useful to save some memory in exchange for a small speed decrease.

		Args:
			slice_size (`str` or `int`, *optional*, defaults to `"auto"`):
				When `"auto"`, halves the input to the attention heads, so attention will be computed in two steps. If
				a number is provided, uses as many slices as `attention_head_dim // slice_size`. In this case,
				`attention_head_dim` must be a multiple of `slice_size`.
		"""
		if slice_size == "auto":
			# half the attention head size is usually a good trade-off between
			# speed and memory
			slice_size = self.unet.config.attention_head_dim // 2
		self.unet.set_attention_slice(slice_size)

	def disable_attention_slicing(self):
		r"""
		Disable sliced attention computation. If `enable_attention_slicing` was previously invoked, this method will go
		back to computing attention in one step.
		"""
		# set slice_size = `None` to disable `attention slicing`
		self.enable_attention_slicing(None)

	@torch.no_grad()
	def __call__(
		self,
		latents,
		**kwargs,
	):
		image = self.vae.decode(latents).sample
		#print('latents:', latents.shape, latents.dtype)

		image = (image / 2 + 0.5).clamp(0, 1)
		image = image.cpu().permute(0, 2, 3, 1).numpy()

		image = self.numpy_to_pil(image)

		return dict(images=image)
