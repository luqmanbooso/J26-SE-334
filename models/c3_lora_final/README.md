---
library_name: peft
license: other
base_model: D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct
tags:
- base_model:adapter:D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct
- llama-factory
- lora
- transformers
pipeline_tag: text-generation
model-index:
- name: c3_lora_boosted_recall
  results: []
---

<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->

# c3_lora_boosted_recall

This model is a fine-tuned version of [D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct](https://huggingface.co/D:\university\Resesarch\RD\models\Qwen2-VL-2B-Instruct) on the c3_train_boosted dataset.

## Model description

More information needed

## Intended uses & limitations

More information needed

## Training and evaluation data

More information needed

## Training procedure

### Training hyperparameters

The following hyperparameters were used during training:
- learning_rate: 5e-05
- train_batch_size: 1
- eval_batch_size: 8
- seed: 42
- gradient_accumulation_steps: 8
- total_train_batch_size: 8
- optimizer: Use OptimizerNames.ADAMW_TORCH with betas=(0.9,0.999) and epsilon=1e-08 and optimizer_args=No additional optimizer arguments
- lr_scheduler_type: cosine
- lr_scheduler_warmup_steps: 15
- num_epochs: 2.0
- mixed_precision_training: Native AMP

### Training results



### Framework versions

- PEFT 0.21.2
- Transformers 5.19.0
- Pytorch 2.6.0+cu124
- Datasets 3.6.0
- Tokenizers 0.23.3