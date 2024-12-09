# -*- coding: utf-8 -*-
"""llama2_quantization.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1GDguRoHYfRn-WLb0Scy78LWfnp8-kEDg
"""

!pip install datasets evaluate bert-score bitsandbytes --quiet
!huggingface-cli login
# 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

import time
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from bert_score import score  # For evaluation


# Evaluation function (using BERTScore)
def evaluate_BERTScore(model, tokenizer, dataset, num_samples=10, prompt_length=400, gen_length=400):
    predictions = []
    references = []
    total_inference_time = 0.0
    memory_usages = []  # To store memory usage for each sample

    for i in range(num_samples):

        if device == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
            initial_memory = torch.cuda.memory_allocated(device) / 1e6  # MB

        text = dataset[i]["text"]
        if len(text) < prompt_length + gen_length:
            continue

        # Split text into prompt and reference
        prompt = text[:prompt_length]
        reference = text[prompt_length : prompt_length + gen_length]

        # Tokenize input
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)

        # Measure inference time and memory usage
        torch.cuda.reset_peak_memory_stats(device)  # Reset memory stats
        start_time = time.time()
        with torch.no_grad():
            outputs = model.generate(**inputs, max_length=gen_length)
        inference_time = time.time() - start_time
        total_inference_time += inference_time

        # Decode prediction
        prediction = tokenizer.decode(outputs[0], skip_special_tokens=True)

        if device == "cuda":
            peak_memory = torch.cuda.max_memory_allocated(device) / 1e6  # MB
            memory_usage = peak_memory - initial_memory
        # Append to lists
        predictions.append(prediction)
        references.append(reference)
        if device == "cuda":
            memory_usages.append(memory_usage)

    # Compute BERTScore
    P, R, F1 = score(predictions, references, lang="en", verbose=True)

    avg_inference_time = total_inference_time / num_samples
    avg_memory_usage = sum(memory_usages) / len(memory_usages) if memory_usages else 0.0

    return {
        "precision": P.mean().item(),
        "recall": R.mean().item(),
        "f1": F1.mean().item(),
        "avg_inference_time": avg_inference_time,
        "avg_memory_usage_mb": avg_memory_usage,
        "max_memory_usage_mb": max(memory_usages) if memory_usages else 0.0,
    }

# Device setup
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load dataset
dataset = load_dataset("wikitext", "wikitext-103-v1")
train_dataset = dataset["train"]

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

# Set up 8-bit quantization using BitsAndBytesConfig
quantization_config = BitsAndBytesConfig(
    load_in_8bit=True,  # Enable 8-bit quantization
    llm_int8_threshold=6.0,  # Default threshold, adjust for performance
    llm_int8_skip_modules=None  # Specify modules to skip if needed
)

# Load the model with the quantization config
teacher_model_name = "meta-llama/Llama-2-7b-hf"
teacher_model = AutoModelForCausalLM.from_pretrained(
    teacher_model_name,
    quantization_config=quantization_config,
    device_map="auto"  # Automatically distribute across GPU/CPU
)

# Load the tokenizer
teacher_tokenizer = AutoTokenizer.from_pretrained(teacher_model_name)
if teacher_tokenizer.pad_token is None:
    teacher_tokenizer.pad_token = teacher_tokenizer.eos_token

print("8-bit quantized model loaded successfully!")

print("Evaluating the quantized model...")
test_dataset = dataset["test"]
results = evaluate_BERTScore(teacher_model, teacher_tokenizer, test_dataset, num_samples=100)

print("\nEvaluation Results:")
print(f"Precision Score (BERTScore): {results['precision']:.4f}")
print(f"Recall Score (BERTScore): {results['recall']:.4f}")
print(f"F1 Score (BERTScore): {results['f1']:.4f}")
print(f"Average Inference Time: {results['avg_inference_time']:.4f}s")
print(f"Average Memory Usage: {results['avg_memory_usage_mb']:.4f}MB")
print(f"Max Memory Usage: {results['max_memory_usage_mb']:.4f}MB")