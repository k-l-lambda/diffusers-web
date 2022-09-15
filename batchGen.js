
import fs from "fs";
import path from "path";
import fetch from "node-fetch";



const fetchOne = async (fetcher, dir) => {
	const response = await fetcher();
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
};


const TOTAL = 3;


const main = async argv => {
	const fetcher = () => fetch(`${argv[2]}/paint-by-text?prompt=***&img_only&w=448&h=896`);
	const dir = argv[3] || "./";

	for (let i = 0; i < TOTAL; ++i) {
		await fetchOne(fetcher, dir);

		if (i % 10 === 0)
			console.log(`${i}/${TOTAL}`);
	}

	console.log("Done.");
};


main(process.argv);
