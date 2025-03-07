# from pathlib import Path; import sys; sys.path.append(str(Path(__file__).resolve().parent.parent))
from lib.proc_init_utils import initialise_tpu
# from lib.proc_init_utils import initialise_gpu; initialise_gpu()

import jax
import jax.numpy as jnp
import jax.random as rand
from jax_smi import initialise_tracking
from transformers import LlamaTokenizer

# from lib.generation import TopKGenerationConfig, top_k
from lib.generation import TopPGenerationConfig, top_p
from lib.llama import model_config_llama2_7B
from lib.multihost_utils import shard_array, shard_model_params
from lib.param_utils import load_params
from lib.seeding import BEST_INTEGER

tokenizer = LlamaTokenizer.from_pretrained('../llama-weights/llama2-7B')
tokenizer.pad_token = tokenizer.eos_token  # TODO: verify this
sentences = [
    'I believe the meaning of life is',
    'Simply put, the theory of relativity states that',
    'Thus, leveraging the potential of quantum computing, we can optimize complex algorithms, paving the way for breakthroughs in fields ranging from cryptography to molecular modeling',
]

def main() -> None:
    initialise_tpu('v4-16', n_devices=8, rank=0)
    is_process_0 = jax.process_index() == 0
    if is_process_0:
        print(jax.devices)
    initialise_tracking()

    key = rand.key(BEST_INTEGER)
    cpu_device = jax.devices('cpu')[0]
    with jax.default_device(cpu_device):
        params = load_params('llama2-7B.pickle')
    params = shard_model_params(params)

    # top_k_config = TopKGenerationConfig(eos_token_id=tokenizer.eos_token_id, max_length=128, top_k=10)
    top_p_config = TopPGenerationConfig(eos_token_id=tokenizer.eos_token_id, max_length=128, top_p=0.9)

    inputs = tokenizer(sentences, max_length=top_p_config.max_length, padding='max_length', return_tensors='jax')
    seq = inputs.input_ids.astype(jnp.uint16)
    attn_mask = inputs.attention_mask.astype(jnp.bool_)

    seq = shard_array(seq, ...)
    attn_mask = shard_array(attn_mask, ...)

    key, subkey = rand.split(key)
    config_llama2_7B_ = model_config_llama2_7B._replace(dropout_rate=None)
    # generated_seq = top_k(params, seq, attn_mask, key=subkey, model_config=model_config_llama1_7B, top_k_config=top_k_config)
    generated_seq = top_p(params, seq, attn_mask, key=subkey, model_config=config_llama2_7B_, top_p_config=top_p_config)
    decoded_texts = tokenizer.batch_decode(generated_seq, skip_special_tokens=True)

    if is_process_0:
        for decoded_text in decoded_texts:
            print(decoded_text, end='\n\n')

if __name__ == '__main__':
    main()
