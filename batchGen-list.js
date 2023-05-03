
import fs from "fs";
import path from "path";
import fetch from "node-fetch";



process.env.NODE_TLS_REJECT_UNAUTHORIZED = "0";


const fetchOne = (fetcher, dir) => {
	const promise = fetcher();
	promise.then(async response => {
			await new Promise(resolve => setTimeout(resolve, 0));

			const [_, filename] = response.headers.get('content-disposition').match(/filename="(.+)"/);
			//console.log("filename:", filename);
	
			// find a unique name
			let fullname = path.resolve(dir, filename);
			let i = 0;
	
			const [stem, ext] = filename.split(".");
			while (fs.existsSync(fullname))
				fullname = path.resolve(dir, `${stem} [${i++}].${ext}`);
	
			const buffer = await response.buffer();
	
			fs.writeFileSync(fullname, buffer);
	}).catch(err => console.warn('res err:', err));

	return promise;
};


const main = async argv => {
	const listText = fs.readFileSync(argv[2]).toString();
	const prompts = listText.split("\r\n");
	const negPrompt = encodeURIComponent("anime, (worst quality, low quality:2), (normal quality:2), distorted fingers, extra fingers, watermarks, text");
	const fetcher = prompt => fetch(`${argv[3]}/paint-by-text?prompt=${encodeURIComponent(prompt)}&neg_prompt=${negPrompt}&img_only&w=512&h=1024&n_steps=50&ext=webp`);
	const dir = argv[4] || "./";

	if (!fs.existsSync(dir))
		fs.mkdirSync(dir);

	let i = 0;
	for (const prompt of prompts) {
		try {
			await fetchOne(() => fetcher("(masterpiece, best quality, beautiful and aesthetic:1.2), (1girl:1.3), photorealistic, " + prompt), dir);
		}
		catch(err) {
			console.warn(i, err);
		}

		if (i++ % 10 === 0)
			console.log(`${i}/${prompts.length}`);
	}

	console.log("Done.");
};


main(process.argv).catch(err => console.log('fatal:', err));
