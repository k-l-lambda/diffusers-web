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
			></div>
		</main>
		<header>
			<button @click="clear">&#x239A;</button>
		</header>
	</div>
</template>

<script>
	import StoreInput from "./storeinput.vue";



	export default {
		name: "painter",


		components: {
			StoreInput,
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
					this.pasteImage(URL.createObjectURL(file));
				}
			},


			onDropFiles(event) {
				this.drageHover = false;

				const file = event.dataTransfer.files[0];
				if (file)
					if (/^image/.test(file.type))
						this.pasteImage(URL.createObjectURL(file));
			},


			async pasteImage (url) {
				const img = new Image();
				img.src = url;
				await new Promise((resolve, reject) => {
					img.onload = resolve;
					img.onerror = reject;
				});

				//console.log('paste:', img, this.pointerPosition);

				this.ctx.drawImage(img, this.pointerPosition.x, this.pointerPosition.y);
			},


			clear () {
				this.ctx.clearRect(0, 0, this.canvasSize.width, this.canvasSize.height);
			},
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
</style>
