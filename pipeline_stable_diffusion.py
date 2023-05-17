
import inspect
#import warnings
from typing import List, Optional, Union, Callable
import base64
import struct
import PIL.Image
import logging
from packaging import version

import numpy as np
import torch

from transformers import CLIPFeatureExtractor, CLIPTextModel, CLIPTokenizer

from diffusers.utils import deprecate
from diffusers.configuration_utils import FrozenDict
from diffusers.models import AutoencoderKL, UNet2DConditionModel
from diffusers.pipeline_utils import DiffusionPipeline
from diffusers.schedulers import (
	DDIMScheduler,
	DPMSolverMultistepScheduler,
	EulerAncestralDiscreteScheduler,
	EulerDiscreteScheduler,
	LMSDiscreteScheduler,
	PNDMScheduler,
)
from diffusers.pipelines.stable_diffusion import StableDiffusionPipelineOutput
from diffusers.pipelines.stable_diffusion.safety_checker import StableDiffusionSafetyChecker



LATENTS_SCALING = 0.18215


def preprocess (image):
	w, h = image.size
	w, h = map(lambda x: x - x % 32, (w, h))  # resize to integer multiple of 32
	image = image.resize((w, h), resample=PIL.Image.LANCZOS)
	image = np.array(image).astype(np.float32) / 255.0
	image = image[None].transpose(0, 3, 1, 2)[:, :3, :, :]
	image = torch.from_numpy(image)
	if image.shape[1] == 1:
		image = image.repeat((1, 3, 1, 1))
	return 2.0 * image - 1.0


#def preprocess_mask(mask):
#	mask = mask.convert("L")
#	w, h = mask.size
#	w, h = map(lambda x: x - x % 32, (w, h))  # resize to integer multiple of 32
#	mask = mask.resize((w // 8, h // 8), resample=PIL.Image.NEAREST)
#	mask = np.array(mask).astype(np.float32) / 255.0
#	mask = np.tile(mask, (4, 1, 1))
#	mask = np.expand_dims(mask, axis=0)
#	#mask = 1 - mask  # repaint white, keep black
#	mask = torch.from_numpy(mask)
#	return mask


def prepare_mask_and_masked_image(image, mask):
	image = np.array(image.convert("RGB"))
	image = image[None].transpose(0, 3, 1, 2)
	image = torch.from_numpy(image).to(dtype=torch.float32) / 127.5 - 1.0

	mask = np.array(mask.convert("L"))
	mask = mask.astype(np.float32) / 255.0
	mask = mask[None, None]
	mask[mask < 0.5] = 0
	mask[mask >= 0.5] = 1
	mask = torch.from_numpy(mask)

	masked_image = image * (mask < 0.5)

	return mask, masked_image


def encodeFloat32 (tensor):
	tensor = tensor.flatten()
	return base64.b64encode(struct.pack('f' * tensor.shape[0], *tensor)).decode('ascii')


class StableDiffusionPipeline (DiffusionPipeline):
	r"""
	Pipeline for text-to-image generation using Stable Diffusion.

	This model inherits from [`DiffusionPipeline`]. Check the superclass documentation for the generic methods the
	library implements for all the pipelines (such as downloading or saving, running on a particular device, etc.)

	Args:
		vae ([`AutoencoderKL`]):
			Variational Auto-Encoder (VAE) Model to encode and decode images to and from latent representations.
		text_encoder ([`CLIPTextModel`]):
			Frozen text-encoder. Stable Diffusion uses the text portion of
			[CLIP](https://huggingface.co/docs/transformers/model_doc/clip#transformers.CLIPTextModel), specifically
			the [clip-vit-large-patch14](https://huggingface.co/openai/clip-vit-large-patch14) variant.
		tokenizer (`CLIPTokenizer`):
			Tokenizer of class
			[CLIPTokenizer](https://huggingface.co/docs/transformers/v4.21.0/en/model_doc/clip#transformers.CLIPTokenizer).
		unet ([`UNet2DConditionModel`]): Conditional U-Net architecture to denoise the encoded image latents.
		scheduler ([`SchedulerMixin`]):
			A scheduler to be used in combination with `unet` to denoise the encoded image latens. Can be one of
			[`DDIMScheduler`], [`LMSDiscreteScheduler`], or [`PNDMScheduler`].
		safety_checker ([`StableDiffusionSafetyChecker`]):
			Classification module that estimates whether generated images could be considered offsensive or harmful.
			Please, refer to the [model card](https://huggingface.co/CompVis/stable-diffusion-v1-4) for details.
		feature_extractor ([`CLIPFeatureExtractor`]):
			Model that extracts features from generated images to be used as inputs for the `safety_checker`.
	"""

	def __init__ (
		self,
		vae: AutoencoderKL,
		text_encoder: CLIPTextModel,
		tokenizer: CLIPTokenizer,
		unet: UNet2DConditionModel,
		scheduler: Union[
			DDIMScheduler,
			PNDMScheduler,
			LMSDiscreteScheduler,
			EulerDiscreteScheduler,
			EulerAncestralDiscreteScheduler,
			DPMSolverMultistepScheduler,
		],
		safety_checker: StableDiffusionSafetyChecker = None,
		feature_extractor: CLIPFeatureExtractor = None,
		requires_safety_checker: bool = False,
	):
		super().__init__()

		if hasattr(scheduler.config, "steps_offset") and scheduler.config.steps_offset != 1:
			deprecation_message = (
				f"The configuration file of this scheduler: {scheduler} is outdated. `steps_offset`"
				f" should be set to 1 instead of {scheduler.config.steps_offset}. Please make sure "
				"to update the config accordingly as leaving `steps_offset` might led to incorrect results"
				" in future versions. If you have downloaded this checkpoint from the Hugging Face Hub,"
				" it would be very nice if you could open a Pull request for the `scheduler/scheduler_config.json`"
				" file"
			)
			deprecate("steps_offset!=1", "1.0.0", deprecation_message, standard_warn=False)
			new_config = dict(scheduler.config)
			new_config["steps_offset"] = 1
			scheduler._internal_dict = FrozenDict(new_config)

		if hasattr(scheduler.config, "clip_sample") and scheduler.config.clip_sample is True:
			deprecation_message = (
				f"The configuration file of this scheduler: {scheduler} has not set the configuration `clip_sample`."
				" `clip_sample` should be set to False in the configuration file. Please make sure to update the"
				" config accordingly as not setting `clip_sample` in the config might lead to incorrect results in"
				" future versions. If you have downloaded this checkpoint from the Hugging Face Hub, it would be very"
				" nice if you could open a Pull request for the `scheduler/scheduler_config.json` file"
			)
			deprecate("clip_sample not set", "1.0.0", deprecation_message, standard_warn=False)
			new_config = dict(scheduler.config)
			new_config["clip_sample"] = False
			scheduler._internal_dict = FrozenDict(new_config)

		is_unet_version_less_0_9_0 = hasattr(unet.config, "_diffusers_version") and version.parse(
			version.parse(unet.config._diffusers_version).base_version
		) < version.parse("0.9.0.dev0")
		is_unet_sample_size_less_64 = hasattr(unet.config, "sample_size") and unet.config.sample_size < 64
		if is_unet_version_less_0_9_0 and is_unet_sample_size_less_64:
			deprecation_message = (
				"The configuration file of the unet has set the default `sample_size` to smaller than"
				" 64 which seems highly unlikely .If you're checkpoint is a fine-tuned version of any of the"
				" following: \n- CompVis/stable-diffusion-v1-4 \n- CompVis/stable-diffusion-v1-3 \n-"
				" CompVis/stable-diffusion-v1-2 \n- CompVis/stable-diffusion-v1-1 \n- runwayml/stable-diffusion-v1-5"
				" \n- runwayml/stable-diffusion-inpainting \n you should change 'sample_size' to 64 in the"
				" configuration file. Please make sure to update the config accordingly as leaving `sample_size=32`"
				" in the config might lead to incorrect results in future versions. If you have downloaded this"
				" checkpoint from the Hugging Face Hub, it would be very nice if you could open a Pull request for"
				" the `unet/config.json` file"
			)
			deprecate("sample_size<64", "1.0.0", deprecation_message, standard_warn=False)
			new_config = dict(unet.config)
			new_config["sample_size"] = 64
			unet._internal_dict = FrozenDict(new_config)

		self.register_modules(
			vae=vae,
			text_encoder=text_encoder,
			tokenizer=tokenizer,
			unet=unet,
			scheduler=scheduler,
			safety_checker=None,
			feature_extractor=None,
		)
		self.vae_scale_factor = 2 ** (len(self.vae.config.block_out_channels) - 1)
		self.register_to_config(requires_safety_checker=False)


	def enable_attention_slicing (self, slice_size: Optional[Union[str, int]] = "auto"):
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

	def disable_attention_slicing (self):
		r"""
		Disable sliced attention computation. If `enable_attention_slicing` was previously invoked, this method will go
		back to computing attention in one step.
		"""
		# set slice_size = `None` to disable `attention slicing`
		self.enable_attention_slicing(None)


	@property
	def _execution_device (self):
		r"""
		Returns the device on which the pipeline's models will be executed. After calling
		`pipeline.enable_sequential_cpu_offload()` the execution device can only be inferred from Accelerate's module
		hooks.
		"""
		if self.device != torch.device("meta") or not hasattr(self.unet, "_hf_hook"):
			return self.device
		for module in self.unet.modules():
			if (
				hasattr(module, "_hf_hook")
				and hasattr(module._hf_hook, "execution_device")
				and module._hf_hook.execution_device is not None
			):
				return torch.device(module._hf_hook.execution_device)
		return self.device


	def _encode_prompt (self, prompt, device, num_images_per_prompt, do_classifier_free_guidance, negative_prompt):
		r"""
		Encodes the prompt into text encoder hidden states.

		Args:
			prompt (`str` or `list(int)`):
				prompt to be encoded
			device: (`torch.device`):
				torch device
			num_images_per_prompt (`int`):
				number of images that should be generated per prompt
			do_classifier_free_guidance (`bool`):
				whether to use classifier free guidance or not
			negative_prompt (`str` or `List[str]`):
				The prompt or prompts not to guide the image generation. Ignored when not using guidance (i.e., ignored
				if `guidance_scale` is less than `1`).
		"""
		batch_size = len(prompt) if isinstance(prompt, list) else 1

		text_inputs = self.tokenizer(
			prompt,
			padding="max_length",
			max_length=self.tokenizer.model_max_length,
			truncation=True,
			return_tensors="pt",
		)
		text_input_ids = text_inputs.input_ids
		untruncated_ids = self.tokenizer(prompt, padding="max_length", return_tensors="pt").input_ids

		if not torch.equal(text_input_ids, untruncated_ids):
			removed_text = self.tokenizer.batch_decode(untruncated_ids[:, self.tokenizer.model_max_length - 1 : -1])
			logging.warning(
				"The following part of your input was truncated because CLIP can only handle sequences up to"
				f" {self.tokenizer.model_max_length} tokens: {removed_text}"
			)

		if hasattr(self.text_encoder.config, "use_attention_mask") and self.text_encoder.config.use_attention_mask:
			attention_mask = text_inputs.attention_mask.to(device)
		else:
			attention_mask = None

		text_embeddings = self.text_encoder(
			text_input_ids.to(device),
			attention_mask=attention_mask,
		)
		text_embeddings = text_embeddings[0]

		# duplicate text embeddings for each generation per prompt, using mps friendly method
		bs_embed, seq_len, _ = text_embeddings.shape
		text_embeddings = text_embeddings.repeat(1, num_images_per_prompt, 1)
		text_embeddings = text_embeddings.view(bs_embed * num_images_per_prompt, seq_len, -1)

		# get unconditional embeddings for classifier free guidance
		if do_classifier_free_guidance:
			uncond_tokens: List[str]
			if negative_prompt is None:
				uncond_tokens = [""] * batch_size
			elif type(prompt) is not type(negative_prompt):
				raise TypeError(
					f"`negative_prompt` should be the same type to `prompt`, but got {type(negative_prompt)} !="
					f" {type(prompt)}."
				)
			elif isinstance(negative_prompt, str):
				uncond_tokens = [negative_prompt]
			elif batch_size != len(negative_prompt):
				raise ValueError(
					f"`negative_prompt`: {negative_prompt} has batch size {len(negative_prompt)}, but `prompt`:"
					f" {prompt} has batch size {batch_size}. Please make sure that passed `negative_prompt` matches"
					" the batch size of `prompt`."
				)
			else:
				uncond_tokens = negative_prompt

			max_length = text_input_ids.shape[-1]
			uncond_input = self.tokenizer(
				uncond_tokens,
				padding="max_length",
				max_length=max_length,
				truncation=True,
				return_tensors="pt",
			)

			if hasattr(self.text_encoder.config, "use_attention_mask") and self.text_encoder.config.use_attention_mask:
				attention_mask = uncond_input.attention_mask.to(device)
			else:
				attention_mask = None

			uncond_embeddings = self.text_encoder(
				uncond_input.input_ids.to(device),
				attention_mask=attention_mask,
			)
			uncond_embeddings = uncond_embeddings[0]

			# duplicate unconditional embeddings for each generation per prompt, using mps friendly method
			seq_len = uncond_embeddings.shape[1]
			uncond_embeddings = uncond_embeddings.repeat(1, num_images_per_prompt, 1)
			uncond_embeddings = uncond_embeddings.view(batch_size * num_images_per_prompt, seq_len, -1)

			# For classifier free guidance, we need to do two forward passes.
			# Here we concatenate the unconditional and text embeddings into a single batch
			# to avoid doing two forward passes
			text_embeddings = torch.cat([uncond_embeddings, text_embeddings])

		return text_embeddings


	def decode_latents(self, latents):
		latents = 1 / 0.18215 * latents
		image = self.vae.decode(latents).sample
		image = (image / 2 + 0.5).clamp(0, 1)
		# we always cast to float32 as this does not cause significant overhead and is compatible with bfloa16
		image = image.cpu().permute(0, 2, 3, 1).float().numpy()
		return image


	def prepare_extra_step_kwargs(self, generator, eta):
		# prepare extra kwargs for the scheduler step, since not all schedulers have the same signature
		# eta (η) is only used with the DDIMScheduler, it will be ignored for other schedulers.
		# eta corresponds to η in DDIM paper: https://arxiv.org/abs/2010.02502
		# and should be between [0, 1]

		accepts_eta = "eta" in set(inspect.signature(self.scheduler.step).parameters.keys())
		extra_step_kwargs = {}
		if accepts_eta:
			extra_step_kwargs["eta"] = eta

		# check if the scheduler accepts generator
		accepts_generator = "generator" in set(inspect.signature(self.scheduler.step).parameters.keys())
		if accepts_generator:
			extra_step_kwargs["generator"] = generator
		return extra_step_kwargs


	def check_inputs(self, prompt, height, width, callback_steps):
		if not isinstance(prompt, str) and not isinstance(prompt, list):
			raise ValueError(f"`prompt` has to be of type `str` or `list` but is {type(prompt)}")

		if height % 8 != 0 or width % 8 != 0:
			raise ValueError(f"`height` and `width` have to be divisible by 8 but are {height} and {width}.")

		if (callback_steps is None) or (
			callback_steps is not None and (not isinstance(callback_steps, int) or callback_steps <= 0)
		):
			raise ValueError(
				f"`callback_steps` has to be a positive integer but is {callback_steps} of type"
				f" {type(callback_steps)}."
			)


	def prepare_latents(self, batch_size, num_channels_latents, height, width, dtype, device, generator, latents=None):
		shape = (batch_size, num_channels_latents, height // self.vae_scale_factor, width // self.vae_scale_factor)
		if latents is None:
			if device.type == "mps":
				# randn does not work reproducibly on mps
				latents = torch.randn(shape, generator=generator, device="cpu", dtype=dtype).to(device)
			else:
				latents = torch.randn(shape, generator=generator, device=device, dtype=dtype)
		else:
			if latents.shape != shape:
				raise ValueError(f"Unexpected latents shape, got {latents.shape}, expected {shape}")
			latents = latents.to(device)

		# scale the initial noise by the standard deviation required by the scheduler
		latents = latents * self.scheduler.init_noise_sigma
		return latents


	@torch.no_grad()
	def generate (
		self,
		prompt: Union[str, List[str]],
		height: Optional[int] = None,
		width: Optional[int] = None,
		num_inference_steps: Optional[int] = 50,
		guidance_scale: Optional[float] = 7.5,
		negative_prompt: Optional[Union[str, List[str]]] = None,
		num_images_per_prompt: Optional[int] = 1,
		eta: Optional[float] = 0.0,
		generator: Optional[torch.Generator] = None,
		latents: Optional[torch.FloatTensor] = None,
		output_type: Optional[str] = "pil",
		return_dict: bool = True,
		callback: Optional[Callable[[int, int, torch.FloatTensor], None]] = None,
		callback_steps: Optional[int] = 1,
		**kwargs,
	):
		r"""
		Function invoked when calling the pipeline for generation.

		Args:
			prompt (`str` or `List[str]`):
				The prompt or prompts to guide the image generation.
			height (`int`, *optional*, defaults to self.unet.config.sample_size * self.vae_scale_factor):
				The height in pixels of the generated image.
			width (`int`, *optional*, defaults to self.unet.config.sample_size * self.vae_scale_factor):
				The width in pixels of the generated image.
			num_inference_steps (`int`, *optional*, defaults to 50):
				The number of denoising steps. More denoising steps usually lead to a higher quality image at the
				expense of slower inference.
			guidance_scale (`float`, *optional*, defaults to 7.5):
				Guidance scale as defined in [Classifier-Free Diffusion Guidance](https://arxiv.org/abs/2207.12598).
				`guidance_scale` is defined as `w` of equation 2. of [Imagen
				Paper](https://arxiv.org/pdf/2205.11487.pdf). Guidance scale is enabled by setting `guidance_scale >
				1`. Higher guidance scale encourages to generate images that are closely linked to the text `prompt`,
				usually at the expense of lower image quality.
			negative_prompt (`str` or `List[str]`, *optional*):
				The prompt or prompts not to guide the image generation. Ignored when not using guidance (i.e., ignored
				if `guidance_scale` is less than `1`).
			num_images_per_prompt (`int`, *optional*, defaults to 1):
				The number of images to generate per prompt.
			eta (`float`, *optional*, defaults to 0.0):
				Corresponds to parameter eta (η) in the DDIM paper: https://arxiv.org/abs/2010.02502. Only applies to
				[`schedulers.DDIMScheduler`], will be ignored for others.
			generator (`torch.Generator`, *optional*):
				A [torch generator](https://pytorch.org/docs/stable/generated/torch.Generator.html) to make generation
				deterministic.
			latents (`torch.FloatTensor`, *optional*):
				Pre-generated noisy latents, sampled from a Gaussian distribution, to be used as inputs for image
				generation. Can be used to tweak the same generation with different prompts. If not provided, a latents
				tensor will ge generated by sampling using the supplied random `generator`.
			output_type (`str`, *optional*, defaults to `"pil"`):
				The output format of the generate image. Choose between
				[PIL](https://pillow.readthedocs.io/en/stable/): `PIL.Image.Image` or `np.array`.
			return_dict (`bool`, *optional*, defaults to `True`):
				Whether or not to return a [`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] instead of a
				plain tuple.
			callback (`Callable`, *optional*):
				A function that will be called every `callback_steps` steps during inference. The function will be
				called with the following arguments: `callback(step: int, timestep: int, latents: torch.FloatTensor)`.
			callback_steps (`int`, *optional*, defaults to 1):
				The frequency at which the `callback` function will be called. If not specified, the callback will be
				called at every step.

		Returns:
			[`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] or `tuple`:
			[`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] if `return_dict` is True, otherwise a `tuple.
			When returning a tuple, the first element is a list with the generated images, and the second element is a
			list of `bool`s denoting whether the corresponding generated image likely represents "not-safe-for-work"
			(nsfw) content, according to the `safety_checker`.
		"""
		# 0. Default height and width to unet
		height = height or self.unet.config.sample_size * self.vae_scale_factor
		width = width or self.unet.config.sample_size * self.vae_scale_factor

		# 1. Check inputs. Raise error if not correct
		self.check_inputs(prompt, height, width, callback_steps)

		# 2. Define call parameters
		batch_size = 1 if isinstance(prompt, str) else len(prompt)
		device = self._execution_device
		# here `guidance_scale` is defined analog to the guidance weight `w` of equation (2)
		# of the Imagen paper: https://arxiv.org/pdf/2205.11487.pdf . `guidance_scale = 1`
		# corresponds to doing no classifier free guidance.
		do_classifier_free_guidance = guidance_scale > 1.0

		# 3. Encode input prompt
		text_embeddings = self._encode_prompt(
			prompt, device, num_images_per_prompt, do_classifier_free_guidance, negative_prompt
		)

		# 4. Prepare timesteps
		self.scheduler.set_timesteps(num_inference_steps, device=device)
		timesteps = self.scheduler.timesteps

		# 5. Prepare latent variables
		num_channels_latents = self.unet.in_channels
		latents = self.prepare_latents(
			batch_size * num_images_per_prompt,
			num_channels_latents,
			height,
			width,
			text_embeddings.dtype,
			device,
			generator,
			latents,
		)

		# 6. Prepare extra step kwargs. TODO: Logic should ideally just be moved out of the pipeline
		extra_step_kwargs = self.prepare_extra_step_kwargs(generator, eta)

		# 7. Denoising loop
		for i, t in enumerate(self.progress_bar(timesteps)):
			# expand the latents if we are doing classifier free guidance
			latent_model_input = torch.cat([latents] * 2) if do_classifier_free_guidance else latents
			latent_model_input = self.scheduler.scale_model_input(latent_model_input, t)

			# predict the noise residual
			noise_pred = self.unet(latent_model_input, t, encoder_hidden_states=text_embeddings).sample

			# perform guidance
			if do_classifier_free_guidance:
				noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
				noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

			# compute the previous noisy sample x_t -> x_t-1
			latents = self.scheduler.step(noise_pred, t, latents, **extra_step_kwargs).prev_sample

			# call the callback, if provided
			if callback is not None and i % callback_steps == 0:
				callback(i, t, latents)

		# 8. Post-processing
		image = self.decode_latents(latents)

		latent_codes = [encodeFloat32(l) for l in latents]

		# 9. Run safety checker
		#image, has_nsfw_concept = self.run_safety_checker(image, device, text_embeddings.dtype)
		has_nsfw_concept = None

		# 10. Convert to PIL
		if output_type == "pil":
			image = self.numpy_to_pil(image)

		if not return_dict:
			return (image, has_nsfw_concept)

		return dict(images=image, latents=latent_codes, nsfw_content_detected=has_nsfw_concept)


	@torch.no_grad()
	def decode (
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


	@torch.no_grad()
	def convert (
		self,
		prompt: Union[str, List[str]],
		init_image: Union[torch.FloatTensor, PIL.Image.Image],
		strength: float = 0.8,
		num_inference_steps: Optional[int] = 50,
		guidance_scale: Optional[float] = 7.5,
		eta: Optional[float] = 0.0,
		generator: Optional[torch.Generator] = None,
		output_type: Optional[str] = "pil",
	):
		r"""
		Function invoked when calling the pipeline for generation.

		Args:
			prompt (`str` or `List[str]`):
				The prompt or prompts to guide the image generation.
			init_image (`torch.FloatTensor` or `PIL.Image.Image`):
				`Image`, or tensor representing an image batch, that will be used as the starting point for the
				process.
			strength (`float`, *optional*, defaults to 0.8):
				Conceptually, indicates how much to transform the reference `init_image`. Must be between 0 and 1.
				`init_image` will be used as a starting point, adding more noise to it the larger the `strength`. The
				number of denoising steps depends on the amount of noise initially added. When `strength` is 1, added
				noise will be maximum and the denoising process will run for the full number of iterations specified in
				`num_inference_steps`. A value of 1, therefore, essentially ignores `init_image`.
			num_inference_steps (`int`, *optional*, defaults to 50):
				The number of denoising steps. More denoising steps usually lead to a higher quality image at the
				expense of slower inference. This parameter will be modulated by `strength`.
			guidance_scale (`float`, *optional*, defaults to 7.5):
				Guidance scale as defined in [Classifier-Free Diffusion Guidance](https://arxiv.org/abs/2207.12598).
				`guidance_scale` is defined as `w` of equation 2. of [Imagen
				Paper](https://arxiv.org/pdf/2205.11487.pdf). Guidance scale is enabled by setting `guidance_scale >
				1`. Higher guidance scale encourages to generate images that are closely linked to the text `prompt`,
				usually at the expense of lower image quality.
			eta (`float`, *optional*, defaults to 0.0):
				Corresponds to parameter eta (η) in the DDIM paper: https://arxiv.org/abs/2010.02502. Only applies to
				[`schedulers.DDIMScheduler`], will be ignored for others.
			generator (`torch.Generator`, *optional*):
				A [torch generator](https://pytorch.org/docs/stable/generated/torch.Generator.html) to make generation
				deterministic.
			output_type (`str`, *optional*, defaults to `"pil"`):
				The output format of the generate image. Choose between
				[PIL](https://pillow.readthedocs.io/en/stable/): `PIL.Image.Image` or `nd.array`.

		Returns:
			[`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] or `tuple`:
			[`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] if `return_dict` is True, otherwise a `tuple.
			When returning a tuple, the first element is a list with the generated images, and the second element is a
			list of `bool`s denoting whether the corresponding generated image likely represents "not-safe-for-work"
			(nsfw) content, according to the `safety_checker`.
		"""
		if isinstance(prompt, str):
			batch_size = 1
		elif isinstance(prompt, list):
			batch_size = len(prompt)
		else:
			raise ValueError(f"`prompt` has to be of type `str` or `list` but is {type(prompt)}")

		if strength < 0 or strength > 1:
			raise ValueError(f"The value of strength should in [0.0, 1.0] but is {strength}")

		# set timesteps
		accepts_offset = "offset" in set(inspect.signature(self.scheduler.set_timesteps).parameters.keys())
		extra_set_kwargs = {}
		offset = 0
		if accepts_offset:
			offset = 1
			extra_set_kwargs["offset"] = 1

		self.scheduler.set_timesteps(num_inference_steps, **extra_set_kwargs)

		if not isinstance(init_image, torch.FloatTensor):
			init_image = preprocess(init_image)
			init_image = init_image.to(self.vae.dtype)

		# encode the init image into latents and scale the latents
		init_latent_dist = self.vae.encode(init_image.to(self.device)).latent_dist
		init_latents = init_latent_dist.sample(generator=generator)
		init_latents = LATENTS_SCALING * init_latents

		# expand init_latents for batch_size
		init_latents = torch.cat([init_latents] * batch_size)

		# get the original timestep using init_timestep
		init_timestep = int(num_inference_steps * strength) + offset
		init_timestep = min(init_timestep, num_inference_steps)
		if isinstance(self.scheduler, LMSDiscreteScheduler):
			timesteps = torch.tensor(
				[num_inference_steps - init_timestep] * batch_size, dtype=torch.long, device=self.device
			)
		else:
			timesteps = self.scheduler.timesteps[-init_timestep]
			timesteps = torch.tensor([timesteps] * batch_size, dtype=torch.long, device=self.device)

		# add noise to latents using the timesteps
		noise = torch.randn(init_latents.shape, generator=generator, device=self.device)
		init_latents = self.scheduler.add_noise(init_latents, noise, timesteps).to(self.device)

		# get prompt text embeddings
		text_input = self.tokenizer(
			prompt,
			padding="max_length",
			max_length=self.tokenizer.model_max_length,
			truncation=True,
			return_tensors="pt",
		)
		text_embeddings = self.text_encoder(text_input.input_ids.to(self.device))[0]

		# here `guidance_scale` is defined analog to the guidance weight `w` of equation (2)
		# of the Imagen paper: https://arxiv.org/pdf/2205.11487.pdf . `guidance_scale = 1`
		# corresponds to doing no classifier free guidance.
		do_classifier_free_guidance = guidance_scale > 1.0
		# get unconditional embeddings for classifier free guidance
		if do_classifier_free_guidance:
			max_length = text_input.input_ids.shape[-1]
			uncond_input = self.tokenizer(
				[""] * batch_size, padding="max_length", max_length=max_length, return_tensors="pt"
			)
			uncond_embeddings = self.text_encoder(uncond_input.input_ids.to(self.device))[0]

			# For classifier free guidance, we need to do two forward passes.
			# Here we concatenate the unconditional and text embeddings into a single batch
			# to avoid doing two forward passes
			text_embeddings = torch.cat([uncond_embeddings, text_embeddings])

		# prepare extra kwargs for the scheduler step, since not all schedulers have the same signature
		# eta (η) is only used with the DDIMScheduler, it will be ignored for other schedulers.
		# eta corresponds to η in DDIM paper: https://arxiv.org/abs/2010.02502
		# and should be between [0, 1]
		accepts_eta = "eta" in set(inspect.signature(self.scheduler.step).parameters.keys())
		extra_step_kwargs = {}
		if accepts_eta:
			extra_step_kwargs["eta"] = eta

		latents = init_latents

		t_start = max(num_inference_steps - init_timestep + offset, 0)
		for i, t in enumerate(self.progress_bar(self.scheduler.timesteps[t_start:])):
			t_index = t_start + i

			# expand the latents if we are doing classifier free guidance
			latent_model_input = torch.cat([latents] * 2) if do_classifier_free_guidance else latents

			# if we use LMSDiscreteScheduler, let's make sure latents are mulitplied by sigmas
			if isinstance(self.scheduler, LMSDiscreteScheduler):
				sigma = self.scheduler.sigmas[t_index]
				# the model input needs to be scaled to match the continuous ODE formulation in K-LMS
				latent_model_input = latent_model_input / ((sigma**2 + 1) ** 0.5)
				latent_model_input = latent_model_input.to(self.unet.dtype)
				t = t.to(self.unet.dtype)

			# predict the noise residual
			noise_pred = self.unet(latent_model_input.to(self.unet.dtype), t.to(self.unet.dtype), encoder_hidden_states=text_embeddings.to(self.unet.dtype)).sample

			# perform guidance
			if do_classifier_free_guidance:
				noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
				noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

			# compute the previous noisy sample x_t -> x_t-1
			if isinstance(self.scheduler, LMSDiscreteScheduler):
				latents = self.scheduler.step(noise_pred, t_index, latents, **extra_step_kwargs).prev_sample
			else:
				latents = self.scheduler.step(noise_pred, t, latents, **extra_step_kwargs).prev_sample

		# scale and decode the image latents with vae
		latents = 1 / LATENTS_SCALING * latents
		image = self.vae.decode(latents.to(self.vae.dtype)).sample

		latent_codes = [encodeFloat32(l) for l in latents]

		image = (image / 2 + 0.5).clamp(0, 1)
		image = image.cpu().permute(0, 2, 3, 1).numpy()

		# run safety checker
		#safety_cheker_input = self.feature_extractor(self.numpy_to_pil(image), return_tensors="pt").to(self.device)
		#image, has_nsfw_concept = self.safety_checker(images=image, clip_input=safety_cheker_input.pixel_values)
		has_nsfw_concept = None

		if output_type == "pil":
			image = self.numpy_to_pil(image)

		return dict(images=image, latents=latent_codes, nsfw_content_detected=has_nsfw_concept)


	@torch.no_grad()
	def inpaint(
		self,
		prompt: Union[str, List[str]],
		image: Union[torch.FloatTensor, PIL.Image.Image],
		mask_image: Union[torch.FloatTensor, PIL.Image.Image],
		num_inference_steps: Optional[int] = 50,
		guidance_scale: Optional[float] = 7.5,
		negative_prompt: Optional[Union[str, List[str]]] = None,
		num_images_per_prompt: Optional[int] = 1,
		eta: Optional[float] = 0.0,
		generator: Optional[torch.Generator] = None,
		latents: Optional[torch.FloatTensor] = None,
		output_type: Optional[str] = "pil",
		callback: Optional[Callable[[int, int, torch.FloatTensor], None]] = None,
		callback_steps: Optional[int] = 1,
	):
		r"""
		Function invoked when calling the pipeline for generation.

		Args:
			prompt (`str` or `List[str]`):
				The prompt or prompts to guide the image generation.
			image (`PIL.Image.Image`):
				`Image`, or tensor representing an image batch which will be inpainted, *i.e.* parts of the image will
				be masked out with `mask_image` and repainted according to `prompt`.
			mask_image (`PIL.Image.Image`):
				`Image`, or tensor representing an image batch, to mask `image`. White pixels in the mask will be
				repainted, while black pixels will be preserved. If `mask_image` is a PIL image, it will be converted
				to a single channel (luminance) before use. If it's a tensor, it should contain one color channel (L)
				instead of 3, so the expected shape would be `(B, H, W, 1)`.
			height (`int`, *optional*, defaults to 512):
				The height in pixels of the generated image.
			width (`int`, *optional*, defaults to 512):
				The width in pixels of the generated image.
			num_inference_steps (`int`, *optional*, defaults to 50):
				The number of denoising steps. More denoising steps usually lead to a higher quality image at the
				expense of slower inference.
			guidance_scale (`float`, *optional*, defaults to 7.5):
				Guidance scale as defined in [Classifier-Free Diffusion Guidance](https://arxiv.org/abs/2207.12598).
				`guidance_scale` is defined as `w` of equation 2. of [Imagen
				Paper](https://arxiv.org/pdf/2205.11487.pdf). Guidance scale is enabled by setting `guidance_scale >
				1`. Higher guidance scale encourages to generate images that are closely linked to the text `prompt`,
				usually at the expense of lower image quality.
			negative_prompt (`str` or `List[str]`, *optional*):
				The prompt or prompts not to guide the image generation. Ignored when not using guidance (i.e., ignored
				if `guidance_scale` is less than `1`).
			num_images_per_prompt (`int`, *optional*, defaults to 1):
				The number of images to generate per prompt.
			eta (`float`, *optional*, defaults to 0.0):
				Corresponds to parameter eta (η) in the DDIM paper: https://arxiv.org/abs/2010.02502. Only applies to
				[`schedulers.DDIMScheduler`], will be ignored for others.
			generator (`torch.Generator`, *optional*):
				A [torch generator](https://pytorch.org/docs/stable/generated/torch.Generator.html) to make generation
				deterministic.
			latents (`torch.FloatTensor`, *optional*):
				Pre-generated noisy latents, sampled from a Gaussian distribution, to be used as inputs for image
				generation. Can be used to tweak the same generation with different prompts. If not provided, a latents
				tensor will ge generated by sampling using the supplied random `generator`.
			output_type (`str`, *optional*, defaults to `"pil"`):
				The output format of the generate image. Choose between
				[PIL](https://pillow.readthedocs.io/en/stable/): `PIL.Image.Image` or `np.array`.
			return_dict (`bool`, *optional*, defaults to `True`):
				Whether or not to return a [`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] instead of a
				plain tuple.
			callback (`Callable`, *optional*):
				A function that will be called every `callback_steps` steps during inference. The function will be
				called with the following arguments: `callback(step: int, timestep: int, latents: torch.FloatTensor)`.
			callback_steps (`int`, *optional*, defaults to 1):
				The frequency at which the `callback` function will be called. If not specified, the callback will be
				called at every step.

		Returns:
			[`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] or `tuple`:
			[`~pipelines.stable_diffusion.StableDiffusionPipelineOutput`] if `return_dict` is True, otherwise a `tuple.
			When returning a tuple, the first element is a list with the generated images, and the second element is a
			list of `bool`s denoting whether the corresponding generated image likely represents "not-safe-for-work"
			(nsfw) content, according to the `safety_checker`.
		"""

		width, height = mask_image.width, mask_image.height

		if isinstance(prompt, str):
			batch_size = 1
		elif isinstance(prompt, list):
			batch_size = len(prompt)
		else:
			raise ValueError(f"`prompt` has to be of type `str` or `list` but is {type(prompt)}")

		if height % 8 != 0 or width % 8 != 0:
			raise ValueError(f"`height` and `width` have to be divisible by 8 but are {height} and {width}.")

		if (callback_steps is None) or (
			callback_steps is not None and (not isinstance(callback_steps, int) or callback_steps <= 0)
		):
			raise ValueError(
				f"`callback_steps` has to be a positive integer but is {callback_steps} of type"
				f" {type(callback_steps)}."
			)

		# get prompt text embeddings
		text_inputs = self.tokenizer(
			prompt,
			padding="max_length",
			max_length=self.tokenizer.model_max_length,
			return_tensors="pt",
		)
		text_input_ids = text_inputs.input_ids

		if text_input_ids.shape[-1] > self.tokenizer.model_max_length:
			removed_text = self.tokenizer.batch_decode(text_input_ids[:, self.tokenizer.model_max_length :])
			logging.warning(
				"The following part of your input was truncated because CLIP can only handle sequences up to"
				f" {self.tokenizer.model_max_length} tokens: {removed_text}"
			)
			text_input_ids = text_input_ids[:, : self.tokenizer.model_max_length]
		text_embeddings = self.text_encoder(text_input_ids.to(self.device))[0]

		# duplicate text embeddings for each generation per prompt, using mps friendly method
		bs_embed, seq_len, _ = text_embeddings.shape
		text_embeddings = text_embeddings.repeat(1, num_images_per_prompt, 1)
		text_embeddings = text_embeddings.view(bs_embed * num_images_per_prompt, seq_len, -1)

		# here `guidance_scale` is defined analog to the guidance weight `w` of equation (2)
		# of the Imagen paper: https://arxiv.org/pdf/2205.11487.pdf . `guidance_scale = 1`
		# corresponds to doing no classifier free guidance.
		do_classifier_free_guidance = guidance_scale > 1.0
		# get unconditional embeddings for classifier free guidance
		if do_classifier_free_guidance:
			uncond_tokens: List[str]
			if negative_prompt is None:
				uncond_tokens = [""]
			elif type(prompt) is not type(negative_prompt):
				raise TypeError(
					f"`negative_prompt` should be the same type to `prompt`, but got {type(negative_prompt)} !="
					f" {type(prompt)}."
				)
			elif isinstance(negative_prompt, str):
				uncond_tokens = [negative_prompt]
			elif batch_size != len(negative_prompt):
				raise ValueError(
					f"`negative_prompt`: {negative_prompt} has batch size {len(negative_prompt)}, but `prompt`:"
					f" {prompt} has batch size {batch_size}. Please make sure that passed `negative_prompt` matches"
					" the batch size of `prompt`."
				)
			else:
				uncond_tokens = negative_prompt

			max_length = text_input_ids.shape[-1]
			uncond_input = self.tokenizer(
				uncond_tokens,
				padding="max_length",
				max_length=max_length,
				truncation=True,
				return_tensors="pt",
			)
			uncond_embeddings = self.text_encoder(uncond_input.input_ids.to(self.device))[0]

			# duplicate unconditional embeddings for each generation per prompt, using mps friendly method
			seq_len = uncond_embeddings.shape[1]
			uncond_embeddings = uncond_embeddings.repeat(batch_size, num_images_per_prompt, 1)
			uncond_embeddings = uncond_embeddings.view(batch_size * num_images_per_prompt, seq_len, -1)

			# For classifier free guidance, we need to do two forward passes.
			# Here we concatenate the unconditional and text embeddings into a single batch
			# to avoid doing two forward passes
			text_embeddings = torch.cat([uncond_embeddings, text_embeddings])

		# get the initial random noise unless the user supplied it
		# Unlike in other pipelines, latents need to be generated in the target device
		# for 1-to-1 results reproducibility with the CompVis implementation.
		# However this currently doesn't work in `mps`.
		num_channels_latents = self.vae.config.latent_channels
		latents_shape = (batch_size * num_images_per_prompt, num_channels_latents, height // 8, width // 8)
		latents_dtype = text_embeddings.dtype
		if latents is None:
			if self.device.type == "mps":
				# randn does not exist on mps
				latents = torch.randn(latents_shape, generator=generator, device="cpu", dtype=latents_dtype).to(
					self.device
				)
			else:
				latents = torch.randn(latents_shape, generator=generator, device=self.device, dtype=latents_dtype)
		else:
			if latents.shape != latents_shape:
				raise ValueError(f"Unexpected latents shape, got {latents.shape}, expected {latents_shape}")
			latents = latents.to(self.device)

		# prepare mask and masked_image
		mask, masked_image = prepare_mask_and_masked_image(image, mask_image)
		mask = mask.to(device=self.device, dtype=text_embeddings.dtype)
		masked_image = masked_image.to(device=self.device, dtype=text_embeddings.dtype)

		# resize the mask to latents shape as we concatenate the mask to the latents
		mask = torch.nn.functional.interpolate(mask, size=(height // 8, width // 8))

		# encode the mask image into latents space so we can concatenate it to the latents
		masked_image_latents = self.vae.encode(masked_image).latent_dist.sample(generator=generator)
		masked_image_latents = LATENTS_SCALING * masked_image_latents

		# duplicate mask and masked_image_latents for each generation per prompt, using mps friendly method
		mask = mask.repeat(batch_size * num_images_per_prompt, 1, 1, 1)
		masked_image_latents = masked_image_latents.repeat(batch_size * num_images_per_prompt, 1, 1, 1)

		mask = torch.cat([mask] * 2) if do_classifier_free_guidance else mask
		masked_image_latents = (
			torch.cat([masked_image_latents] * 2) if do_classifier_free_guidance else masked_image_latents
		)

		num_channels_mask = mask.shape[1]
		num_channels_masked_image = masked_image_latents.shape[1]

		if num_channels_latents + num_channels_mask + num_channels_masked_image != self.unet.config.in_channels:
			raise ValueError(
				f"Incorrect configuration settings! The config of `pipeline.unet`: {self.unet.config} expects"
				f" {self.unet.config.in_channels} but received `num_channels_latents`: {num_channels_latents} +"
				f" `num_channels_mask`: {num_channels_mask} + `num_channels_masked_image`: {num_channels_masked_image}"
				f" = {num_channels_latents+num_channels_masked_image+num_channels_mask}. Please verify the config of"
				" `pipeline.unet` or your `mask_image` or `image` input."
			)

		# set timesteps
		self.scheduler.set_timesteps(num_inference_steps)

		# Some schedulers like PNDM have timesteps as arrays
		# It's more optimized to move all timesteps to correct device beforehand
		timesteps_tensor = self.scheduler.timesteps.to(self.device)

		# scale the initial noise by the standard deviation required by the scheduler
		latents = latents * self.scheduler.init_noise_sigma

		# prepare extra kwargs for the scheduler step, since not all schedulers have the same signature
		# eta (η) is only used with the DDIMScheduler, it will be ignored for other schedulers.
		# eta corresponds to η in DDIM paper: https://arxiv.org/abs/2010.02502
		# and should be between [0, 1]
		accepts_eta = "eta" in set(inspect.signature(self.scheduler.step).parameters.keys())
		extra_step_kwargs = {}
		if accepts_eta:
			extra_step_kwargs["eta"] = eta

		for i, t in enumerate(self.progress_bar(timesteps_tensor)):
			# expand the latents if we are doing classifier free guidance
			latent_model_input = torch.cat([latents] * 2) if do_classifier_free_guidance else latents

			# concat latents, mask, masked_image_latents in the channel dimension
			latent_model_input = torch.cat([latent_model_input, mask, masked_image_latents], dim=1)

			latent_model_input = self.scheduler.scale_model_input(latent_model_input, t)

			# predict the noise residual
			noise_pred = self.unet(latent_model_input, t, encoder_hidden_states=text_embeddings).sample

			# perform guidance
			if do_classifier_free_guidance:
				noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
				noise_pred = noise_pred_uncond + guidance_scale * (noise_pred_text - noise_pred_uncond)

			# compute the previous noisy sample x_t -> x_t-1
			latents = self.scheduler.step(noise_pred, t, latents, **extra_step_kwargs).prev_sample

			# call the callback, if provided
			if callback is not None and i % callback_steps == 0:
				callback(i, t, latents)

		latents = 1 / LATENTS_SCALING * latents
		image = self.vae.decode(latents).sample

		image = (image / 2 + 0.5).clamp(0, 1)

		# we always cast to float32 as this does not cause significant overhead and is compatible with bfloa16
		image = image.cpu().permute(0, 2, 3, 1).float().numpy()

		'''if self.safety_checker is not None:
			safety_checker_input = self.feature_extractor(self.numpy_to_pil(image), return_tensors="pt").to(
				self.device
			)
			image, has_nsfw_concept = self.safety_checker(
				images=image, clip_input=safety_checker_input.pixel_values.to(text_embeddings.dtype)
			)
		else:'''
		has_nsfw_concept = None

		if output_type == "pil":
			image = self.numpy_to_pil(image)

		return dict(images=image, nsfw_content_detected=has_nsfw_concept)
