<template>
	<div class="painter"
		@paste="onPaste"
	>
		<main ref="main">
			<canvas class="canvas" ref="canvas"
				:width="canvasSize.width" :height="canvasSize.height"
			/>
			<div class="bench"
				:style="{
					width: `${canvasSize.width}px`,
					height: `${canvasSize.height}px`,
				}"
				@mousemove="pointerPosition.x = $event.offsetX; pointerPosition.y = $event.offsetY"
			>
				<ResizeBox class="diffuser-box"
					:left.sync="diffuserBox.left"
					:right.sync="diffuserBox.right"
					:top.sync="diffuserBox.top"
					:bottom.sync="diffuserBox.bottom"
					@released="onBoxResized"
				/>
			</div>
		</main>
		<header>
			<StoreInput sessionKey="description" type="text" v-model="description" v-show="false" />
			<StoreInput sessionKey="n_steps" type="number" v-model="n_steps"  v-show="false" />
			<StoreInput sessionKey="strength" type="number" v-model="strength" v-show="false" />
			<section>
				<button @click="clear">&#x239A;</button>
				<button @click="copy">&#x2398;</button>
				<button @click="download">&#x2913;</button>
			</section>
			<section>
				<input class="description" v-model="description" type="text" placeholder="prompt text" />
				<input type="number" v-model.number="n_steps" min="1" max="250" style="width: 2em" />
				<input type="range" v-model.number="strength" min="0" max="1" step="any" style="width: 3em" />
				<em title="strength">{{strength.toFixed(2)}}</em>
				<button @click="inpaint">&#x1f58c;</button>
			</section>
		</header>
	</div>
</template>

<script>
	import StoreInput from "./storeinput.vue";
	import ResizeBox from "./resizeBox.vue";

	import {downloadURL} from "./utils";



	const ROUND_UNIT = 32;
	const PIXEL_MAX = 640 * 640;



	export default {
		name: "painter",


		components: {
			StoreInput,
			ResizeBox,
		},


		data () {
			return {
				canvasSize: {
					width: 1280,
					height: 720,
				},
				pointerPosition: {
					x: 0,
					y: 0,
				},
				diffuserBox: {
					left: 200,
					right: 712,
					top: 200,
					bottom: 712,
				},
				description: "",
				n_steps: 50,
				strength: 0.5,
			};
		},


		mounted () {
			this.canvasSize.width = this.$refs.main.clientWidth;
			this.canvasSize.height = this.$refs.main.clientHeight;

			this.ctx = this.$refs.canvas.getContext("2d");
		},


		methods: {
			onPaste(event) {
				const image = [...event.clipboardData.items].filter(item => item.type.match(/image/))[0];
				if (image) {
					const file = image.getAsFile();
					this.pasteImage(URL.createObjectURL(file), this.pointerPosition.x, this.pointerPosition.y);
				}
			},


			onDropFiles(event) {
				this.drageHover = false;

				const file = event.dataTransfer.files[0];
				if (file)
					if (/^image/.test(file.type))
						this.pasteImage(URL.createObjectURL(file), this.pointerPosition.x, this.pointerPosition.y);
			},


			async pasteImage (url, x, y) {
				const img = new Image();
				img.src = url;
				await new Promise((resolve, reject) => {
					img.onload = resolve;
					img.onerror = reject;
				});

				//console.log('paste:', img, this.pointerPosition);

				this.ctx.drawImage(img, x, y);
			},


			clear () {
				this.ctx.clearRect(0, 0, this.canvasSize.width, this.canvasSize.height);
			},


			async copy () {
				const blob = await new Promise(resolve => this.$refs.canvas.toBlob(resolve, "image/png"));
				const result = await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
				console.log("copy:", result);
			},


			async download () {
				const blob = await new Promise(resolve => this.$refs.canvas.toBlob(resolve, "image/png"));
				downloadURL(URL.createObjectURL(blob), `[painter]${Date.now().toString()}.png`);
			},


			onBoxResized (tx, ty) {
				const width = this.diffuserBox.right - this.diffuserBox.left;
				const height = this.diffuserBox.bottom - this.diffuserBox.top;
				let rw = Math.round(width / ROUND_UNIT) * ROUND_UNIT;
				let rh = Math.round(height / ROUND_UNIT) * ROUND_UNIT;

				if (rw * rh > PIXEL_MAX) {
					if (ty)
						rh = PIXEL_MAX / rw;
					else
						rw = PIXEL_MAX / rh;
				}

				if (rw !== width) {
					switch (tx) {
					case "l":
						this.diffuserBox.left = this.diffuserBox.right - rw;
						break;
					case "r":
						this.diffuserBox.right = this.diffuserBox.left + rw;
						break;
					}
				}

				if (rh !== height) {
					switch (ty) {
					case "t":
						this.diffuserBox.top = this.diffuserBox.bottom - rh;
						break;
					case "b":
						this.diffuserBox.bottom = this.diffuserBox.top + rh;
						break;
					}
				}
			},


			async getImageBlock (box) {
				const data = this.ctx.getImageData(box.left, box.top, box.right - box.left, box.bottom - box.top);
				const canvas = document.createElement("canvas");
				canvas.width = data.width;
				canvas.height = data.height;
				const ctx = canvas.getContext("2d");
				ctx.putImageData(data, 0, 0);

				return new Promise(resolve => canvas.toBlob(resolve, "image/png"));
			},


			async inpaint () {
				const image = await this.getImageBlock(this.diffuserBox);

				const form = new FormData();
				form.append("image", image);

				const response = await fetch(`/inpaint?prompt=${encodeURIComponent(this.description)}&n_steps=${this.n_steps}&strength=${this.strength}`, {
					method: "POST",
					body: form,
				});
				const result = await response.blob();
				//console.log("result:", result);

				this.pasteImage(URL.createObjectURL(result), this.diffuserBox.left, this.diffuserBox.top);
			},
		},


		watch: {
		},
	};
</script>

<style src="./common.css"></style>
<style>
	.painter
	{
		height: 100%;
	}

	.painter header
	{
		position: absolute;
		top: 1em;
		left: 50%;
		transform: translate(-50%, 0);
		font-size: 28px;
		padding: .4em 2em;
		background: #fffa;
		border-radius: 1em;
		opacity: 0;
		transition: opacity .4s;
	}

	.painter header:hover
	{
		opacity: 1;
	}

	.painter header *
	{
		font-size: inherit;
	}

	.painter header > * > *
	{
		height: unset;
	}

	.painter main
	{
		height: 100%;
		overflow: hidden;
		position: relative;
	}

	.canvas
	{
		background-repeat: repeat;
		background-image: url('/transparent-bg.svg');
		display: block;
	}

	main .bench
	{
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
	}

	.diffuser-box
	{
		border: dashed 2px #111;
	}
</style>