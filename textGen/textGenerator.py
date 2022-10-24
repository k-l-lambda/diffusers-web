
#import math
import torch
import re



def clipTokenizerWrap (tokenizer):
	def run (text):
		return tokenizer(text)['input_ids'][:-1]

	return run


def clipTokenizerWrapInv (tokenizer):
	def run (ids):
		words = [tokenizer._convert_id_to_token(id) for id in ids.tolist()]
		sentence = ''.join(words)
		sentence = re.sub(r'<\|\w+\|>', '', sentence)
		sentence = re.sub(r'<\/w>,', ',', sentence)
		sentence = re.sub(r'<\/w>\.', '.', sentence)
		sentence = re.sub(r'<\/w>', ' ', sentence)
		sentence = re.sub(r'(?P<n>\d+) k,', '\g<n>k,', sentence)
		sentence = re.sub(r'\s+$', '', sentence)

		return sentence

	return run


def textGenSample (model, tokens2ids, ids2tokens, leading_text='', eos=2, temperature=1, model_max_length=77, length_limit=1000):
	ids = torch.tensor(tokens2ids(leading_text), dtype=torch.long)

	while True:
		if ids[-1].item() == eos or ids.shape[0] >= length_limit:
			break

		with torch.no_grad():
			output = model(ids[None, -model_max_length:])[0]
			weights = torch.exp((output[-1] / temperature).clip(max=80.))
			next_id = torch.multinomial(weights, 1)

			ids = torch.cat((ids, torch.tensor([next_id], dtype=torch.long)))

	return ids2tokens(ids)
