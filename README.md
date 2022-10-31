# Diffusers Web

## Local Enviroment Variables
Edit local enviroment variables in file *.env.local*.

Variable Name						| Default Value						| Description
:--									| :--								| :--
**HF_TOKEN**						|									| Your HuggingFace access token. If a local config path provided, this can be ignored.
**DIFFUSER_MODEL_PATH**				| CompVis/stable-diffusion-v1-4		| This can be a local model config path.
**TEXTGEN_MODEL_PATH**				| k-l-lambda/clip-text-generator	| The random painting description generator model path. This can be a local model config path.
**HTTP_HOST**						| 127.0.0.1							|
**HTTP_PORT**						| 8157								|
**SSL_CONTEXT**						| None								| Use `'adhoc'` for https server.
**DEVICE**							|									| `cuda` or *None*
**TEXT_DEVICE_INDEX**				| 0									| This can be greater than 0 if **CUDA_VISIBLE_DEVICES** has more than 1 gpu specified.
