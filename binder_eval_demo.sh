# Copyright 2025 ByteDance and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

dtype=fp32
use_deepspeed_evo_attention=false
layernorm_type="${LAYERNORM_TYPE:-}"

export LAYERNORM_TYPE=${layernorm_type}
export USE_DEEPSPEED_EVO_ATTENTION=${use_deepspeed_evo_attention}
export TOOL_WEIGHTS_ROOT="${TOOL_WEIGHTS_ROOT:-$(pwd)/tool_weights}"
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

# ===============================
# Tool Weights Sanity Check
# ===============================
ROOT="${TOOL_WEIGHTS_ROOT}"
declare -a REQUIRED_FILES=(
  # ---- AF2 ----
  "$ROOT/af2/params_model_1.npz"
  "$ROOT/af2/params_model_1_ptm.npz"
)
echo "Checking tool weights in: $ROOT"
for f in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo -e "\nMissing required tool weight:"
    echo "   $f"
    echo -e "\nPlease run:"
    echo "   bash download_tool_weights.sh"
    exit 1
  fi
done

# ===============================
# Main
# ===============================
input_root="${INPUT_ROOT:-./examples/pxdesign_binders}"
orig_seqs_root="${ORIG_SEQS_ROOT:-./examples/orig_seqs}"
dump_root="${DUMP_ROOT:-./output/binder}"
skip_existing="${SKIP_EXISTING:-true}"

binder_chains="B0"
is_mmcif=true
N_seqs=2
mpnn_temp=0.0001

if [[ ! -d "${input_root}" ]]; then
  echo "Missing binder input root: ${input_root}"
  exit 1
fi

if [[ -n "${TARGETS:-}" ]]; then
  read -r -a target_list <<< "${TARGETS}"
else
  mapfile -t target_list < <(find "${input_root}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
fi

echo "Binder eval demo"
echo "  input_root:     ${input_root}"
echo "  orig_seqs_root: ${orig_seqs_root}"
echo "  dump_root:      ${dump_root}"
echo "  skip_existing:  ${skip_existing}"
echo "  targets:        ${target_list[*]}"

for target in "${target_list[@]}"; do
  input_dir="${input_root}/${target}"
  dump_dir="${dump_root}/${target}"
  orig_seqs_json="${orig_seqs_root}/orig_seqs_${target}.json"

  if [[ ! -d "${input_dir}" ]]; then
    echo "Missing target input directory: ${input_dir}"
    exit 1
  fi
  if [[ ! -f "${orig_seqs_json}" ]]; then
    echo "Missing original sequence JSON: ${orig_seqs_json}"
    exit 1
  fi
  if [[ "${skip_existing}" == "true" \
        && -f "${dump_dir}/sample_level_output.csv" \
        && -f "${dump_dir}/summary_output.json" ]]; then
    echo "=================================================="
    echo "Skip target ${target}: found ${dump_dir}/sample_level_output.csv and summary_output.json"
    continue
  fi

  echo "=================================================="
  echo "Running binder eval for target: ${target}"
  python3 -m protdbench.run \
  --data_dir "${input_dir}" \
  --dump_dir "${dump_dir}" \
  --is_mmcif ${is_mmcif} \
  --seed 2025 \
  --orig_seqs_json "${orig_seqs_json}" \
  --binder.num_seqs ${N_seqs} \
  --binder.tools.mpnn.temperature ${mpnn_temp} \
  --binder.tools.af2.use_binder_template true \
  --binder.tools.ptx_mini.dtype ${dtype} \
  --binder.tools.ptx_mini.use_deepspeed_evo_attention ${use_deepspeed_evo_attention} \
  --binder_chains ${binder_chains} \
  --binder.use_gt_seq false
done
