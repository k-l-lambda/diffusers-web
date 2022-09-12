
import sys
import os
import re
import flask
import json
import io
import PIL.Image
import base64

import env
from pipeline_stable_diffusion import StableDiffusionPipeline
from pipeline_stable_diffusion_img2img import StableDiffusionImg2ImgPipeline



app = flask.Flask(__name__, static_url_path = '', static_folder = './static')


DIST_DIR = './dist'

HTTP_HOST = os.getenv('HTTP_HOST')
HTTP_PORT = int(os.getenv('HTTP_PORT'))
HF_TOKEN = os.getenv('HF_TOKEN')
DEVICE = os.getenv('DEVICE')


@app.route('/bundles/<path:filename>')
def bundle(filename):
	if re.match(r'.*\.bundle\.js$', filename):
		return flask.send_from_directory(DIST_DIR, filename)

	flask.abort(404, 'Invalid request path.')


pageRouters = {
	'/':				'index.html',
}
for path in pageRouters:
	def getHandler(filename):
		return lambda: flask.send_from_directory(DIST_DIR, filename)

	app.route(path, endpoint = 'handler' + path)(getHandler(pageRouters[path]))


def encodeImageToDataURL (image):
	fp = io.BytesIO()
	image.save(fp, PIL.Image.registered_extensions()['.png'])

	return 'data:image/png;base64,%s' % base64.b64encode(fp.getvalue()).decode('ascii')


@app.route('/paint-by-text', methods=['GET'])
def paintByText():
	prompt = flask.request.args.get('prompt')
	multi = int(flask.request.args.get('multi', 1))
	n_steps = int(flask.request.args.get('n_steps', 50))
	width = int(flask.request.args.get('w', 512))
	height = int(flask.request.args.get('h', 512))
	#print('paint by text:', prompt, multi)

	global pipe
	result = pipe([prompt] * multi, num_inference_steps=n_steps, width=width, height=height)

	result = {
		'prompt': prompt,
		'images': list(map(encodeImageToDataURL, result['images'])),
		'latents': result['latents'],
	}

	return flask.Response(json.dumps(result), mimetype = 'application/json')


@app.route('/img2img', methods=['POST'])
def img2img():
	prompt = flask.request.args.get('prompt')
	n_steps = int(flask.request.args.get('n_steps', 50))
	strength = float(flask.request.args.get('strength', 0.5))

	imageFile = flask.request.files.get('image')
	if not imageFile:
		flask.abort(400, 'image field is requested.')

	image = PIL.Image.open(imageFile.stream)

	w, h = image.size
	large_edge = max(w, h)
	scaling = 1 if large_edge < 1024 else 1024 / large_edge
	w, h = round(w * scaling / 64.) * 64, round(h * scaling / 64.) * 64
	image = image.resize((w, h), resample=PIL.Image.Resampling.BICUBIC)

	global pipe2
	result = pipe2(prompt, init_image=image, num_inference_steps=n_steps, strength=strength)

	result = {
		'prompt': prompt,
		'image': encodeImageToDataURL(result['images'][0]),
		'latent': result['latents'][0],
	}

	return flask.Response(json.dumps(result), mimetype = 'application/json')


def main(argv):
	global pipe, pipe2
	pipe = StableDiffusionPipeline.from_pretrained("CompVis/stable-diffusion-v1-4", use_auth_token=HF_TOKEN)
	pipe2 = StableDiffusionImg2ImgPipeline.from_pretrained("CompVis/stable-diffusion-v1-4", use_auth_token=HF_TOKEN)
	if DEVICE:
		pipe.to(DEVICE)

	try:
		app.run(port=HTTP_PORT, host=HTTP_HOST, threaded=False)
	except:
		print('server interrupted:', sys.exc_info())



if __name__ == "__main__":
	main(sys.argv)
