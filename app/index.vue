<template>
	<div class="home">
		<header>
			<input class="description" v-model="description" type="text" placeholder="prompt text" />
			<StoreInput sessionKey="description" type="text" v-model="description" v-show="false" />
			<StoreInput sessionKey="n_steps" type="number" v-model="n_steps" v-show="false" />
			<StoreInput sessionKey="multi" type="number" v-model="multi" v-show="false" />
			<StoreInput sessionKey="size_w" type="number" v-model="width" v-show="false" />
			<StoreInput sessionKey="size_h" type="number" v-model="height" v-show="false" />
			<input type="number" v-model.number="n_steps" min="1" max="250" :size="1" />
			<select v-model.number="multi">
				<option v-for="i of 4" :key="i" :value="i">{{i}}</option>
			</select>
			<span>
				<select v-model.number="width">
					<option v-for="i of 14" :key="i" :value="64 * (i + 2)">{{64 * (i + 2)}}</option>
				</select>
				&times;
				<select v-model.number="height">
					<option v-for="i of 14" :key="i" :value="64 * (i + 2)">{{64 * (i + 2)}}</option>
				</select>
			</span>
			<button @click="paintByText">&#x1f4ad;</button>
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
				multi: 1,
				n_steps: 50,
				width: 512,
				height: 512,
			};
		},


		methods: {
			async paintByText () {
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
	.home
	{
		display: flex;
		flex-direction: column;
		height: 100%;
	}

	header button
	{
		flex: 0 0 4em;
	}
</style>
