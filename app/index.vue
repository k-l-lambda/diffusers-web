<template>
	<div>
		<header>
			<input v-model="description" type="text" />
			<button @click="paintByText">dream</button>
		</header>
	</div>
</template>

<script>
	export default {
		name: "index",


		data () {
			return {
				description: null,
			};
		},


		methods: {
			async paintByText () {
				const response = await fetch(`/paint-by-text?prompt=${encodeURIComponent(this.description)}&multi=1`);
				const result = await response.json();
				console.log("result:", result);
			},
		},
	};
</script>

<style src="./common.css"></style>
<style>
	body
	{
		white-space: nowrap;
	}

	header
	{
		height: 2em;
		margin: 20px 0;
	}
</style>
