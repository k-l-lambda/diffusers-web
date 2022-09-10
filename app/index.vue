<template>
	<div class="home">
		<header>
			<input v-model="description" type="text" />
			<button @click="paintByText">dream</button>
		</header>
		<main>
			<section v-for="(result, i) of results" :key="i">
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
				const response = await fetch(`/paint-by-text?prompt=${encodeURIComponent(this.description)}&multi=1`);
				const result = await response.json();
				console.log("result:", result);

				this.results.push(result);
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
	}

	main
	{
		overflow-y: auto;
		flex: 1 1;
	}
</style>
