from __future__ import annotations

from typing import List, Optional

from .code_extract import extract_go_code


class BaseGenerator:
    def generate(self, prompt: str, temperature: Optional[float] = None) -> Optional[str]:
        raise NotImplementedError

    def generate_group(self, prompt: str, count: int, temperature: Optional[float] = None) -> List[Optional[str]]:
        return [self.generate(prompt, temperature=temperature) for _ in range(count)]


class EchoGenerator(BaseGenerator):
    """Deterministic fallback used for tests and dry runs."""

    def __init__(self, program: str = "package main\nfunc main() {}\n"):
        self.program = program

    def generate(self, prompt: str, temperature: Optional[float] = None) -> Optional[str]:
        return self.program


class HFGenerator(BaseGenerator):
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.8,
        max_new_tokens: int = 2048,
        context_length: int = 8192,
        batch_size: int = 1,
    ):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto",
            torch_dtype=(
                torch.bfloat16
                if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
                else torch.float16
            ),
            trust_remote_code=True,
        ).eval()
        self.temperature = temperature
        self.max_new_tokens = max_new_tokens
        self.context_length = context_length
        self.batch_size = batch_size

    def generate(self, prompt: str, temperature: Optional[float] = None) -> Optional[str]:
        try:
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=self.context_length,
            ).to(self.model.device)
            with self.torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    attention_mask=inputs.attention_mask,
                    do_sample=True,
                    temperature=self.temperature if temperature is None else temperature,
                    max_new_tokens=self.max_new_tokens,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            generated_ids = outputs[0][inputs.input_ids.shape[1]:]
            text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
            return extract_go_code(text)
        except self.torch.cuda.OutOfMemoryError:
            self.torch.cuda.empty_cache()
            return None


def build_generator(config) -> BaseGenerator:
    if config.backend == "echo" or not config.name:
        return EchoGenerator()
    return HFGenerator(
        model_name=config.name,
        temperature=config.temperature,
        max_new_tokens=config.max_new_tokens,
        context_length=config.context_length,
        batch_size=config.batch_size,
    )

