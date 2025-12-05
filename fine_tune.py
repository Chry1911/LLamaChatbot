from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
from datasets import load_dataset
from peft import LoraConfig, get_peft_model

model_name = "meta-llama/Llama-2-7b-chat-hf"
dataset = load_dataset("json", data_files="dataset.json")

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, device_map="auto")

peft_config = LoraConfig(task_type="CAUSAL_LM", r=16, lora_alpha=32, lora_dropout=0.1)
model = get_peft_model(model, peft_config)

args = TrainingArguments(
    output_dir="./trained_model",
    per_device_train_batch_size=1,
    num_train_epochs=1,
    fp16=True,
    save_steps=50
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=dataset["train"]
)

trainer.train()
model.save_pretrained("./llama-custom")
