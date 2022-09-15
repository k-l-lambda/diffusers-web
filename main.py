
import sys
import os
import re
import flask
import json
import io
import PIL.Image
import base64
import math
import torch

import env
from pipeline_stable_diffusion import StableDiffusionPipeline
from sentenceGen import SentenceGenerator



app = flask.Flask(__name__, static_url_path = '', static_folder = './static')


DIST_DIR = './dist'

HTTP_HOST = os.getenv('HTTP_HOST')
HTTP_PORT = int(os.getenv('HTTP_PORT'))
HF_TOKEN = os.getenv('HF_TOKEN')
MODEL_NAME = os.getenv('MODEL_NAME')
DEVICE = os.getenv('DEVICE')
TEXT_DEVICE_INDEX = os.getenv('TEXT_DEVICE_INDEX')

TEMPERATURE = 4.


@app.route('/bundles/<path:filename>')
def bundle(filename):
	if re.match(r'.*\.bundle\.js$', filename):
		return flask.send_from_directory(DIST_DIR, filename)

	flask.abort(404, 'Invalid request path.')


pageRouters = {
	'/':				'index.html',
	'/converter':		'converter.html',
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
def paintByText ():
	prompt = flask.request.args.get('prompt')
	multi = int(flask.request.args.get('multi', 1))
	n_steps = int(flask.request.args.get('n_steps', 50))
	width = int(flask.request.args.get('w', 512))
	height = int(flask.request.args.get('h', 512))
	img_only = flask.request.args.get('img_only')
	#print('paint by text:', prompt, multi)

	if prompt == '***':
		prompt = senGen.generate(temperature=TEMPERATURE)

	global pipe
	result = pipe.generate([prompt] * multi, num_inference_steps=n_steps, width=width, height=height)

	if img_only is not None:
		fp = io.BytesIO()
		result['images'][0].save(fp, PIL.Image.registered_extensions()['.png'])

		res = flask.Response(fp.getvalue(), mimetype = 'image/png')

		filename = re.sub(r'[^\w\s]', '', prompt)[:240]
		res.headers['Content-Disposition'] = f'inline; filename="{filename}.png"'

		return res

	result = {
		'prompt': prompt,
		'images': list(map(encodeImageToDataURL, result['images'])),
		'latents': result['latents'],
	}

	return flask.Response(json.dumps(result), mimetype = 'application/json')


@app.route('/img2img', methods=['POST'])
def img2img ():
	prompt = flask.request.args.get('prompt')
	n_steps = int(flask.request.args.get('n_steps', 50))
	strength = float(flask.request.args.get('strength', 0.5))

	imageFile = flask.request.files.get('image')
	if not imageFile:
		flask.abort(400, 'image field is requested.')

	image = PIL.Image.open(imageFile.stream)

	PIXELS_SIZE = 640 * 640
	w, h = image.size
	scaling = 1 if w * h <= PIXELS_SIZE else math.sqrt(PIXELS_SIZE / (w * h))
	w, h = round(w * scaling / 64.) * 64, round(h * scaling / 64.) * 64
	if w != image.size[0] or h != image.size[1]:
		image = image.resize((w, h), resample=PIL.Image.BICUBIC)
	#print('image:', image.size, scaling)

	global pipe
	result = pipe.convert(prompt, init_image=image, num_inference_steps=n_steps, strength=strength)

	result = {
		'prompt': prompt,
		'source': encodeImageToDataURL(image),
		'image': encodeImageToDataURL(result['images'][0]),
		'latent': result['latents'][0],
	}

	return flask.Response(json.dumps(result), mimetype = 'application/json')


@app.route('/random-sentence', methods=['GET'])
def randomSentence ():
	global senGen

	return flask.Response(senGen.generate(temperature=TEMPERATURE), mimetype = 'text/plain')


def main (argv):
	global pipe, senGen
	pipe = StableDiffusionPipeline.from_pretrained(MODEL_NAME, use_auth_token=HF_TOKEN)

	device = torch.device(f'{DEVICE}:{TEXT_DEVICE_INDEX}') if DEVICE else None
	senGen = SentenceGenerator(templates_path='corpus/templates.txt', reserved_path='corpus/reserved.txt', device=device)
	if DEVICE:
		pipe.to(DEVICE)

	try:
		app.run(port=HTTP_PORT, host=HTTP_HOST, threaded=False)
	except:
		print('server interrupted:', sys.exc_info())



if __name__ == "__main__":
	main(sys.argv)
