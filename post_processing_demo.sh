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

set -euo pipefail

# Run `bash binder_eval_demo.sh` first. This script consumes its direct output:
#   output/binder/<Target>/sample_level_output.csv
eval_dir="${EVAL_DIR:-./output/binder}"
sample_root="${SAMPLE_ROOT:-./examples/pxdesign_binders}"
# MODEL_NAME is optional — defaults to the eval_dir's directory name if unset.
model_name="${MODEL_NAME:-}"
filter_name="${FILTER_NAME:-af2_easy}"
binder_chain="${BINDER_CHAIN:-B}"
workers="${WORKERS:-1}"
output_dir="${OUTPUT_DIR:-./output/post_processing_demo}"

if [[ ! -d "${eval_dir}" ]]; then
  echo "Missing binder eval output directory: ${eval_dir}"
  echo "Please run: bash binder_eval_demo.sh"
  exit 1
fi

if [[ ! -d "${sample_root}" ]]; then
  echo "Missing raw sample root for cluster-SR: ${sample_root}"
  exit 1
fi

common_args=(
  --eval-dir "${eval_dir}"
  --output "${output_dir}"
)

if [[ -n "${model_name}" ]]; then
  common_args+=(--model-name "${model_name}")
fi

if [[ -n "${TARGETS:-}" ]]; then
  read -r -a target_list <<< "${TARGETS}"
  common_args+=(--targets "${target_list[@]}")
fi

echo "Post-processing demo"
echo "  eval_dir:    ${eval_dir}"
echo "  sample_root: ${sample_root}"
echo "  model_name:  ${model_name:-(auto from eval_dir)}"
echo "  output_dir:  ${output_dir}"
if [[ -n "${TARGETS:-}" ]]; then
  echo "  targets:     ${target_list[*]}"
else
  echo "  targets:     auto"
fi

python3 -m protdbench.post_processing.cli success-rate "${common_args[@]}"
python3 -m protdbench.post_processing.cli alpha-ratio "${common_args[@]}"
python3 -m protdbench.post_processing.cli secondary-structure "${common_args[@]}"
python3 -m protdbench.post_processing.cli cluster-success-rate \
  "${common_args[@]}" \
  --sample-root "${sample_root}" \
  --filter "${filter_name}" \
  --binder-chain "${binder_chain}" \
  --workers "${workers}"

echo "Done. Outputs written to ${output_dir}"
