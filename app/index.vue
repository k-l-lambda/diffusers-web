<template>
	<div class="home">
		<header>
			<input class="description" v-model="description" type="text" placeholder="prompt text" />
			<input class="neg-decription" v-model="negativeDescription" type="text" placeholder="negative prompt text" />
			<button @click="rollDescription" title="Give me an idea.">&#x1f3b2;</button>
			<StoreInput localKey="description" type="text" v-model="description" v-show="false" />
			<StoreInput localKey="negativeDescription" type="text" v-model="negativeDescription" v-show="false" />
			<StoreInput localKey="n_steps" type="number" v-model="n_steps" v-show="false" />
			<StoreInput localKey="seed" type="number" v-model="seed" v-show="false" />
			<StoreInput localKey="multi" type="number" v-model="multi" v-show="false" />
			<StoreInput localKey="size_w" type="number" v-model="width" v-show="false" />
			<StoreInput localKey="size_h" type="number" v-model="height" v-show="false" />
			<input type="number" v-model.number="n_steps" min="1" max="250" :size="1" />
			<input type="text" v-model.number="seed" placeholder="seed" :size="1" />
			<select v-model.number="multi">
				<option v-for="i of 4" :key="i" :value="i">{{i}}</option>
			</select>
			<span>
				<select v-model.number="width">
					<option v-for="i of 30" :key="i" :value="64 * (i + 2)">{{64 * (i + 2)}}</option>
				</select>
				&times;
				<select v-model.number="height">
					<option v-for="i of 30" :key="i" :value="64 * (i + 2)">{{64 * (i + 2)}}</option>
				</select>
			</span>
			<button class="submit" :class="{active: requesting}" @click="paintByText">&#x1f4ad;</button>
		</header>
		<main ref="main">
			<section v-for="(result, i) of results" :key="i">
				<div>
					<button class="activate" @click="activateItem(result)">^</button>
					<em v-text="result.prompt"></em>
					<i v-if="result.negative" :title="result.negative">&#x2d31;</i>
					<span v-if="Number.isFinite(result.seed)">[{{result.seed}}]</span>
					<span v-if="result.loading">...</span>
				</div>
				<div v-if="result.images">
					<div class="picture" v-for="(img, ii) of result.images" :key="ii">
						<img :src="img" @load="onImageLoad" />
						<a class="download" :href="img" :download="`${result.prompt && result.prompt.replace(/[^\w\s]/g, '').substr(0, 240)}.png`">&#x2913;</a>
					</div>
				</div>
				<p v-if="result.error" class="error" v-html="result.error"></p>
				<hr />
			</section>
		</main>
		<button class="purge" @click="purgeList">&#x2421;</button>
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
				negativeDescription: null,
				results: [],
				multi: 1,
				n_steps: 50,
				width: 512,
				height: 512,
				seed: null,
				requesting: false,
			};
		},


		created () {
			window.$main = this;
		},


		methods: {
			async paintByText () {
				const item = {
					prompt: this.description,
					negative: this.negativeDescription,
					seed: this.seed,
					loading: true,
				};
				this.results.push(item);
				this.requesting = true;

				let url = `/paint-by-text?prompt=${encodeURIComponent(this.description || "")}&multi=${this.multi}&n_steps=${this.n_steps}&w=${this.width}&h=${this.height}`;
				if (Number.isInteger(this.seed))
					url += `&seed=${this.seed}`;
				if (this.negativeDescription)
					url += `&neg_prompt=${encodeURIComponent(this.negativeDescription)}`;

				const response = await fetch(url);
				if (response.ok) {
					const result = await response.json();
					if (result.images)
						result.images = await Promise.all(result.images.map(toBlobURL));

					Object.assign(item, result);
				}
				else
					item.error = await response.text();

				item.loading = false;
				this.requesting = false;
			},


			async rollDescription (event) {
				const begin = event.shiftKey ? this.description : "";
				const response = await fetch(`/random-sentence-v2?begin=${begin}`);
				this.description = await response.text();
			},


			onImageLoad () {
				this.$refs.main.scrollTo(0, this.$refs.main.scrollHeight);
			},


			activateItem (item) {
				this.description = item.prompt;
				this.negativeDescription = item.negative;
				this.seed = item.seed;
			},


			purgeList () {
				if (confirm("clear results?"))
					this.results = [];
			}
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
		position: relative;
	}

	.submit.active
	{
		background-color: #cfc;
	}

	.purge
	{
		display: inline-block;
		position: absolute;
		bottom: 8px;
		right: 8px;
		background: none;
		border: 0;
		font-size: 200%;
		color: #aaa;
	}

	i
	{
		font-weight: bold;
		font-style: normal;
		cursor: default;
		color: #600;
	}

	.activate
	{
		margin-right: 1em;
		border: 0;
	}
</style>
