from huggingface_hub import login

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

token = 'TOKEN'
login(token)

model_id = "meta-llama/Prompt-Guard-86M"

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForSequenceClassification.from_pretrained(model_id)


def check_injection(s):
    inputs = tokenizer(s, return_tensors="pt")

    with torch.no_grad():
        logits = model(**inputs).logits

    predicted_class_id = logits.argmax().item()
    is_inj = model.config.id2label[predicted_class_id]

    return True if is_inj == 'INJECTION' else False

