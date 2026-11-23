"""Optional GPU training entry point; not used by the dependency-free demo.

Install independently: pip install 'trl>=0.19' datasets
Review the installed TRL version and hardware requirements before a real run.
"""
import argparse
from datasets import load_dataset
from trl import GRPOConfig, GRPOTrainer
from helix.verifiers import grpo_reward

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True)
parser.add_argument("--model", required=True, help="A compatible local or Hugging Face causal model")
parser.add_argument("--output", default="checkpoints/helix-grpo")
args = parser.parse_args()
dataset = load_dataset("json", data_files=args.data, split="train")
if not len(dataset):
    raise ValueError("No verified training records")
trainer = GRPOTrainer(
    model=args.model,
    reward_funcs=grpo_reward,
    args=GRPOConfig(output_dir=args.output, num_generations=4,
                    per_device_train_batch_size=4, max_completion_length=256),
    train_dataset=dataset,
)
trainer.train()
