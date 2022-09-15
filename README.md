# Diffusers Web

## Local Enviroment Variables
Edit local enviroment variables in file *.env.local*.

Variable Name						| Default Value						| Description
:--									| :--								| :--
**HF_TOKEN**						|									|
**MODEL_NAME**						| CompVis/stable-diffusion-v1-4		| This can be a local model config path.
**HTTP_HOST**						| 127.0.0.1							|
**HTTP_PORT**						| 8157								|
**DEVICE**							|									| cuda or *None*
**TEXT_DEVICE_INDEX**				| 0									| This can be greater than 0 if `CUDA_VISIBLE_DEVICES` has more than 1 gpu specified.
