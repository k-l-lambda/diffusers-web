<template>
	<div class="home">
		<header>
			<input class="description" v-model="description" type="text" />
			<button @click="paintByText">&#x1f4ad;</button>
		</header>
		<main>
			<section v-for="(result, i) of results" :key="i">
				<div><em>{{result.prompt}}</em><span v-if="result.loading">...</span></div>
				<div v-if="result.images">
					<img v-for="(img, ii) of result.images" :key="ii"
						:src="img"
					/>
				</div>
				<hr />
			</section>
		</main>
	</div>
</template>

<script>
	export default {
		name: "index",


		data () {
			return {
				description: null,
				results: [],
			};
		},


		methods: {
			async paintByText () {
				const item = {
					prompt: this.description,
					loading: true,
				};
				this.results.push(item);

				const response = await fetch(`/paint-by-text?prompt=${encodeURIComponent(this.description)}&multi=1&n_steps=50&w=512&h=512`);
				const result = await response.json();
				//console.log("result:", result);

				Object.assign(item, result);
				item.loading = false;
			},
		},
	};
</script>

<style src="./common.css"></style>
<style>
	body
	{
		white-space: nowrap;
		margin: 0;
		height: 100vh;
	}

	.home
	{
		display: flex;
		flex-direction: column;
		height: 100%;
	}

	header
	{
		margin: 20px 0;
		padding: 0 1em;
		flex: 0 0 2em;
		display: flex;
	}

	header .description
	{
		flex: 1 1;
	}

	header button
	{
		flex: 0 0 4em;
	}

	main
	{
		overflow-y: auto;
		flex: 1 1;
	}

	main section
	{
		padding: 1em;
	}
</style>
