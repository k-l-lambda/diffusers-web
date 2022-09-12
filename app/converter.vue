<template>
	<div class="converter"
		@paste="onPaste"
		@drop.prevent="onDropFiles"
		@dragover.prevent="drageHover = true"
		@drageleave="drageHover = false"
		@mouseup="drageHover = false"
	>
		<header>
			<img class="source" :src="sourceURL" :class="{'drop-hover': drageHover}" />
			<input class="description" v-model="description" type="text" placeholder="prompt text" />
			<StoreInput sessionKey="description" type="text" v-model="description" min="1" v-show="false" />
			<StoreInput sessionKey="n_steps" type="number" v-model="n_steps" min="1" v-show="false" />
			<input type="number" v-model="n_steps" min="1" max="250" :size="1" />
			<button @click="paint">&#x1f4ad;</button>
		</header>
		<main>
			<section v-for="(result, i) of results" :key="i">
				<div><em v-text="result.prompt"></em><span v-if="result.loading">...</span></div>
				<div v-if="result.images">
					<div class="picture" v-for="(img, ii) of result.images" :key="ii">
						<img :src="img" />
						<a class="download" :href="img" :download="`${result.prompt && result.prompt.replace(/[^\w\s]/g, '').substr(0, 240)}.png`">&#x2913;</a>
					</div>
				</div>
				<p v-if="result.error" class="error" v-html="result.error"></p>
				<hr />
			</section>
		</main>
	</div>
</template>

<script>
	import StoreInput from "./storeinput.vue";



	const toBlobURL = async url => {
		const blob = await (await fetch(url)).blob();
		return URL.createObjectURL(blob);
	};



	export default {
		name: "index",


		components: {
			StoreInput,
		},


		data () {
			return {
				description: null,
				results: [],
				n_steps: 50,
				sourceURL: null,
				drageHover: false,
			};
		},


		methods: {
			onPaste(event) {
				const image = [...event.clipboardData.items].filter(item => item.type.match(/image/))[0];
				if (image) {
					const file = image.getAsFile();
					this.sourceURL = URL.createObjectURL(file);
				}
			},


			async onDropFiles(event) {
				this.drageHover = false;

				const file = event.dataTransfer.files[0];
				if (file)
					if (/^image/.test(file.type))
						this.sourceURL = URL.createObjectURL(file);
			},


			async paint () {
				const item = {
					prompt: this.description,
					loading: true,
				};
				this.results.push(item);

				const response = await fetch(`/paint-by-text?prompt=${encodeURIComponent(this.description)}&multi=${this.multi}&n_steps=${this.n_steps}&w=${this.width}&h=${this.height}`);
				if (response.ok) {
					const result = await response.json();
					if (result.images)
						result.images = await Promise.all(result.images.map(toBlobURL));

					Object.assign(item, result);
				}
				else
					item.error = await response.text();

				item.loading = false;
			},
		},
	};
</script>

<style src="./common.css"></style>
<style>
	.converter
	{
		display: flex;
		flex-direction: column;
		height: 100%;
	}

	header button
	{
		flex: 0 0 4em;
	}

	header .source
	{
		min-width: 64px;
		width: 64px;
		max-height: 128px;
		vertical-align: top;
	}

	.source.drop-hover
	{
		outline: 4px lightgreen dashed;
	}
</style>
