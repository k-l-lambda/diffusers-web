
import random
import math
import numpy as np
from transformers import BertTokenizer, pipeline



class SentenceGenerator:
	def __init__(self, templates_path, reserved_path):
		self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
		self.unmasker = pipeline('fill-mask', model='bert-base-uncased')

		with open(reserved_path, 'r') as file:
			text = file.read()
			self.reserved_words = text.split('\n')

		with open(templates_path, 'r') as file:
			text = file.read()
			sentences = text.split('\n')

			self.templates = [self.tokenize(sentence) for sentence in sentences]


	def tokenize (self, sentence):
		return self.tokenizer.basic_tokenizer.tokenize(sentence, never_split=self.tokenizer.all_special_tokens)


	def transform_sentence (self, sentence, temperature=1):
		idx = [i for i, word in enumerate(sentence) if not word in self.reserved_words]

		if len(idx) <= 0:
			return sentence

		mid = idx[random.randrange(0, len(idx))]

		masked_sentence = ' '.join([word if i != mid else '[MASK]' for i, word in enumerate(sentence)])
		candidates = self.unmasker(masked_sentence)

		scores = [item['score'] for item in candidates]
		logits = [math.log(s) for s in scores]
		scores = [math.exp(logit / temperature) for logit in logits]
		score_sum = sum(scores)
		scores = [s / score_sum for s in scores]

		samples = np.random.multinomial(1, scores)
		index = list(samples).index(1)

		new_sentence = [word if i != mid else candidates[index]['token_str'] for i, word in enumerate(sentence)]

		return new_sentence
