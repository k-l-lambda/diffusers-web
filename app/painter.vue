<template>
	<div class="painter">
		<header>
		</header>
		<main ref="main">
			<canvas class="canvas" :width="canvasSize.width" :height="canvasSize.height"/>
		</main>
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
			};
		},


		mounted () {
			this.canvasSize.width = this.$refs.main.clientWidth;
			this.canvasSize.height = this.$refs.main.clientHeight;
		},


		methods: {
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
	}

	.painter main
	{
		height: 100%;
		overflow: hidden;
	}

	.canvas
	{
		background-repeat: repeat;
		background-image: url('/transparent-bg.svg');
		display: block;
		margin: 0 auto;
	}
</style>
