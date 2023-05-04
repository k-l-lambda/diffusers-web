
import fs from "fs";
import path from "path";
import fetch from "node-fetch";



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


const TOTAL = 5;


const main = async argv => {
	const negPrompt = encodeURIComponent("(worst quality, low quality:2), (normal quality:2), watermarks");
	const fetcher = () => fetch(`${argv[2]}/paint-by-text?prompt=${encodeURI('(masterpiece, best quality, beautiful and aesthetic:1.2), ')}**&neg_prompt=${negPrompt}&img_only&w=768&h=1024&ext=webp&n_steps=60`);
	const dir = argv[3] || "./";

	if (!fs.existsSync(dir))
		fs.mkdirSync(dir);

	for (let i = 0; i < TOTAL; ++i) {
		try {
			await fetchOne(fetcher, dir);
		}
		catch(err) {
			console.warn(i, err);
		}

		if (i % 10 === 0)
			console.log(`${i}/${TOTAL}`);
	}

	console.log("Done.");
};


main(process.argv).catch(err => console.log('fatal:', err));
