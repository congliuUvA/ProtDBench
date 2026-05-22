# ProtDBench: A Unified Evaluation Suite for Protein Design

This repository provides a comprehensive suite of tools for protein design evaluation, integrating multiple state-of-the-art models with standardized pipelines. It supports both monomer and binder design, enabling thorough assessment across diverse aspects of protein design.


## 📂 Repository Structure

The codebase is organized into three main components:

- `metrics`: Scripts for evaluating multiple aspects of protein design, including sequence quality, structure quality, and designability.

- `tasks`: Pipelines for executing specific protein design evaluations (e.g., monomer, binder).

- `tools`: Wrappers for external models (e.g., Protenix, ProteinMPNN, AlphaFold2, ESMFold) to streamline integration.

### Supported Tasks & Tools
| **Task**   | **Sequence Generation** | **Structure Consistency**             |
|------------|-------------------------|---------------------------------------|
| **Monomer**| ProteinMPNN             | 🔹 ESMFold                            |
| **Binder** | ProteinMPNN             | 🔹 AlphaFold2 <br> 🔹 Protenix         |

---
<a name="install"></a>
## 📦 Installation

ProtDBench supports two installation methods:

- ✅ **One-click installation script (Recommended)**
- 🐳 **Docker-based installation**

---

<a name="one-click-install"></a>
### ✅ One-Click Installation Script (Recommended)

We provide an installation script ``install.sh`` that sets up an  environment and installs all dependencies.

#### What the installer will do

1. Create a dedicated conda / mamba / micromamba environment  
2. Install **PyTorch** matching your specified CUDA version  
3. Install **Protenix**
4. Install **ProtDBench**
5. Run **basic import sanity checks**  

#### Supported options

```bash
--env <name>           Environment name (default: protdbench)
--pkg_manager <tool>   conda | mamba | micromamba (default: conda)
--cuda-version <ver>   CUDA version string, e.g. 12.1, 12.2, 12.4
                        Required. Must be >= 12.1.
```

Example:

```bash
bash install.sh --env protdbench --pkg_manager conda --cuda-version 12.1
```

---

<a name="install-docker"></a>
### 🐳 Docker-Based Installation

#### Step 1: Build the Docker Image

```bash
docker build -t protdbench -f Dockerfile .
```

#### Step 2: Start the Container

```bash
docker run -it --gpus all protdbench bash
```

#### Step 3: Install ProtDBench in the Container

Inside the container:

```bash
git clone https://github.com/congliuUvA/ProtDBench.git
cd ProtDBench
pip install -e .
```


## 📥 Download Required Model Weights (**Required**)

ProtDBench relies on several external pretrained models (e.g., AF2, ProteinMPNN, etc.) for evaluation.  
These **weights are not bundled with the Python package and must be downloaded manually**.

After installing ProtDBench, run:

```bash
bash download_tool_weights.sh
```

This script will automatically download and organize all required pretrained weights for:

- AlphaFold2
- ESMFold
- ProteinMPNN

Model weights for external tools are expected to be organized in a directory as follows:
```
├── af2
│   ├── LICENSE
│   ├── params_model_{1..5}.npz
│   ├── params_model_{1..5}_ptm.npz
│   ├── params_model_{1..5}_multimer_v3.npz
│
├── esmfold
│   ├── config.json
│   ├── pytorch_model.bin
│   ├── special_tokens_map.json
│   ├── tokenizer_config.json
│   └── vocab.txt
│
├── mpnn
│   ├── ca_model_weights/...
│   ├── soluble_model_weights/...
│   └── vanilla_model_weights/...
```
**Note:** Required Protenix files (weights, CCD files, etc.) will be auto-downloaded on the first evaluation run.

---

## 🚀 Quickstart: 3-step workflow

The end-to-end flow for users who have their own designed binders:

```text
┌────────────────────────┐    ┌─────────────────┐    ┌────────────────────────┐
│ 1. Place your designs  │    │ 2. Run eval     │    │ 3. Post-process        │
│                        │    │                 │    │                        │
│ examples/<my_method>/  │ ─► │ binder_eval_    │ ─► │ post_processing_       │
│   <Target>/*.cif       │    │  demo.sh        │    │  demo.sh               │
│                        │    │                 │    │                        │
│ + orig_seqs JSON       │    │ → output/binder │    │ → 4 summary CSVs       │
└────────────────────────┘    └─────────────────┘    └────────────────────────┘
```

### Step 1 — drop your designs in

For each target you want to evaluate, put the designed binders (mmCIF or PDB)
under one directory per target:

```
examples/<my_method>/
  BHRF1/
    BHRF1_design_0.cif
    BHRF1_design_1.cif
    ...
  IL7RA/
    IL7RA_design_0.cif
    ...
```

Plus, for binder eval, one ground-truth sequence JSON per target:

```
examples/orig_seqs/orig_seqs_<Target>.json
```

(see [`examples/pxdesign_binders/`](examples/pxdesign_binders) and
[`examples/orig_seqs/`](examples/orig_seqs) for the bundled demo).

### Step 2 — run the eval pipeline

```bash
INPUT_ROOT=./examples/<my_method> bash binder_eval_demo.sh
```

For each target, this runs ProteinMPNN sequence design + AF2-IG / Protenix-Mini
verifiers, and writes:

```
output/binder/<Target>/sample_level_output.csv
```

It also auto-converts your `.cif` inputs to `.pdb` under
`<my_method>/<Target>/converted_pdbs/` (needed by the cluster post-processing).

### Step 3 — post-process

```bash
SAMPLE_ROOT=./examples/<my_method> bash post_processing_demo.sh
```

(The `Model` column in the output CSVs defaults to the eval-output directory
name. Set `MODEL_NAME=<my_method>` to override it.)

Produces 4 CSVs under `output/post_processing_demo/`:

| CSV | Content |
|---|---|
| `per_sequence_success_rate.csv` | per-design success rate (AF2-IG-Easy / Protenix-Mini / consistency) |
| `alpha_helix_ratio_<aggr>.csv` | per-backbone α-helix ratio |
| `secondary_structure.csv` | iPAE / iPTM stratified by α-vs-β |
| `cluster_success_rate_<filter>.csv` | TMalign cluster-level SR at 3 TM thresholds |

Each analysis also prints a summary table to the terminal. See
[`protdbench/post_processing/README.md`](protdbench/post_processing/README.md) for details on the
Python API and adding new analyses.

---

## 🚀 Running the Evaluation
We provide demo scripts for both monomer and binder design evaluation.
**Monomer evaluation example:**
```bash
bash monomer_eval_demo.sh
```

**Binder evaluation example:**
```bash
bash binder_eval_demo.sh
```

### Input Formats

ProtDBench supports multiple input modes, allowing you to evaluate protein designs flexibly.  
The basic CLI arguments are:
- ``--data_dir``: Directory containing input structures.
- ``--dump_dir``: Output directory for evaluation results.
- ``--is_mmcif``: Flag indicating whether input files are in **mmCIF** format (otherwise assumed **PDB**).

**JSON-based Input**
One can also provide a JSON configuration file describing the evaluation task. This format allows fine-grained control over task parameters and is particularly useful for batch evaluation.

Example JSON:
```python
{
    "task": ...,          # "monomer" or "binder"
    "pdb_dir": ...,       # directory containing the input PDB structures
    "name": ...,          # name of the task; used to locate "{pdb_dir}/{pdb_name}.pdb"
    "pdb_names": ...,     # list of PDB file names to evaluate 
    "cond_chains": ...,   # list of condition chains (only for binder evaluation)
    "binder_chains": ..., # list of binder chains (binder evaluation only; currently supports **one** binder chain)
    "out_dir": ...        # directory to store evaluation results
}
```
Key points:

- Binder tasks require `binder_chains` to be explicitly specified.
- Currently only one binder chain is supported; all other chains will be treated as condition chains.
- `pdb_names` defines the exact structures to evaluate. If omitted, all files in `pdb_dir` with valid suffixes will be evaluated.

**Directory-based Input**
Instead of JSON, one may provide a directory path directly to `--data_dir`.
In this case:

- If `file_name_list` is provided, only matching files will be evaluated.
- Otherwise, all files in the directory with valid extensions will be included.


### Binder Evaluation with Additional Metadata

Binder evaluation supports passing a JSON file to specify additional metadata beyond the default inputs.  
This is useful for advanced scenarios such as:

1. **Evaluating cropped sequences**  
   - If the sequence to be evaluated is a cropped segment of an original sequence, you can provide the **full original sequence** along with a `crop` field to specify the range used in evaluation.  
   - The crop range can be multiple ranges such as `"1-120,130-150"` (comma-separated ranges, 1-based indexing, inclusive).

2. **Providing precomputed MSA for Protenix filter**  
   - The Protenix filter requires the target chain's MSA.  
   - By default, the evaluation script will automatically call the Protenix MSA server to compute the MSA.  
   - If you have already computed the MSA locally, you can skip the server call by specifying the `msa` field with:
     - `precomputed_msa_dir`: Path to the local MSA directory.
     - `pairing_db`: `uniref100`.

**Example JSON input:**
```json
[
    {
        "proteinChain": {
            "sequence": "NAFTVTVPKDLYVVEYGSNMTIECKFPVEKQLDLAALIVYWEMEDKNIIQFVHGEEDLKVQHSSYRQRARLLKDQLSLGNAALQITDVKLQDAGVYRCMISYGGADYKRITVKVNA",
            "label_asym_id": ["A0"],
            "use_msa": true,
            "msa": {
                "precomputed_msa_dir": "examples/msa/PDL1/0",
                "pairing_db": "uniref100"
            },
            "crop": "1-116"
        }
    }
]
```

### Multi-GPU / Distributed Evaluation
ProtDBench exposes device IDs for each integrated model, enabling:
- Deployment across multiple GPUs for **parallel evaluation**.
- Integration into **DDP (Distributed Data Parallel)** training pipelines for **online evaluation tracking**.

For example, the following is a pseudocode snippet illustrating online evaluation tracking in the DDP model training pipeline:
```python
from protdbench.run import run_task
from protenix.utils.distributed import DIST_WRAPPER

@torch.no_grad()
def _evaluate_design(self):
    # Sampling stage
    self._inference_design()
    DIST_WRAPPER.barrier()

    # Load task list
    with open(self._get_eval_json_path(), "r") as f:
        all_eval_tasks = json.load(f)

    # Distribute tasks among workers
    task_indices = list(range(len(all_eval_tasks)))[DIST_WRAPPER.rank::DIST_WRAPPER.world_size]
    if not task_indices:
        self.local_print("No task to evaluate, skipping.")
        results = []
    else:
        self.local_print(f"Running {len(task_indices)} tasks...")
        results = [
            run_task(all_eval_tasks[i], self.configs.eval, device_id=DIST_WRAPPER.local_rank)
            for i in task_indices
        ]

    # Gather results
    all_eval_results = DIST_WRAPPER.all_gather_object(results)
    # Custom logging...
```

### Evaluation Process

- If `use_gt_seq=True`, the sequence from the input structure is used directly.
- If `use_gt_seq=False`, the tool will first run the assigned sequence generation model (e.g., ProteinMPNN) to generate sequences.
- Structure quality is then assessed using the corresponding structure prediction models:
  - Monomer → ESMFold
  - Binder → AlphaFold2 / Protenix
- Metrics include:
  - Self-consistency between predicted structures
  - Confidence scores from structure predictors (e.g., pLDDT, ipTM)
  - Shape-based metrics, e.g. secondary structure content (α-helix, β-sheet, loop ratios), radius of gyration, etc.
- Results are stored in a summary CSV for downstream analysis.

### Post-processing

The recommended entry point is the [`protdbench/post_processing/`](protdbench/post_processing/)
package — it consumes `output/binder/<Target>/sample_level_output.csv` and
writes 4 summary CSVs (per-design SR, α-helix ratio, SS-stratified iPAE /
iPTM, TMalign cluster SR). One-shot demo:

```bash
bash post_processing_demo.sh
```

Or invoke a single analysis:

```bash
python -m protdbench.post_processing.cli success-rate \
  --eval-dir ./output/binder \
  --output ./figs

python -m protdbench.post_processing.cli cluster-success-rate \
  --eval-dir ./output/binder \
  --sample-root ./examples/<my_method> \
  --filter af2_easy \
  --binder-chain B
```

See [`protdbench/post_processing/README.md`](protdbench/post_processing/README.md) for the full
list of analyses, the Python API, and how to extend it.

The lower-level `protdbench/scripts/postprocess_binder.py` (called by
cluster-SR under the hood) and `postprocess_monomer.py` are still available
if you want to drive TMalign / Foldseek clustering manually:

```bash
python3 protdbench/scripts/postprocess_monomer.py --input_dir examples/monomer
python3 protdbench/scripts/postprocess_binder.py --input_dir examples/binder --is_mmcif true
```

`postprocess_monomer.py` requires Foldseek, which is **not** bundled —
install it separately:
[Foldseek Installation](https://github.com/steineggerlab/foldseek#installation).

---

## 📚 Citing Related Work
If you use this repository, please cite the following works:

<details>
<summary>PXDesign</summary>

```bibtex
@article{ren2025pxdesign,
  title={PXDesign: Fast, Modular, and Accurate De Novo Design of Protein Binders},
  author={Ren, Milong and Sun, Jinyuan and Guan, Jiaqi and Liu, Cong and Gong, Chengyue and Wang, Yuzhe and Wang, Lan and Cai, Qixu and Chen, Xinshi and Xiao, Wenzhi},
  journal={bioRxiv},
  pages={2025--08},
  year={2025},
  publisher={Cold Spring Harbor Laboratory}
}
```
</details>

<details>
<summary>Protenix</summary>

```bibtex
@article{bytedance2025protenix,
  title={Protenix - Advancing Structure Prediction Through a Comprehensive AlphaFold3 Reproduction},
  author={ByteDance AML AI4Science Team and Chen, Xinshi and Zhang, Yuxuan and Lu, Chan and Ma, Wenzhi and Guan, Jiaqi and Gong, Chengyue and Yang, Jincai and Zhang, Hanyu and Zhang, Ke and Wu, Shenghao and Zhou, Kuangqi and Yang, Yanping and Liu, Zhenyu and Wang, Lan and Shi, Bo and Shi, Shaochen and Xiao, Wenzhi},
  year={2025},
  journal={bioRxiv},
  publisher={Cold Spring Harbor Laboratory},
  doi={10.1101/2025.01.08.631967},
  URL={https://www.biorxiv.org/content/early/2025/01/11/2025.01.08.631967},
  elocation-id={2025.01.08.631967},
  eprint={https://www.biorxiv.org/content/early/2025/01/11/2025.01.08.631967.full.pdf},
}
```
</details>

<details>
<summary>ProteinMPNN</summary>

```bibtex
@article{dauparas2022robust,
  title={Robust deep learning--based protein sequence design using ProteinMPNN},
  author={Dauparas, Justas and Anishchenko, Ivan and Bennett, Nathaniel and Bai, Hua and Ragotte, Robert J and Milles, Lukas F and Wicky, Basile IM and Courbet, Alexis and de Haas, Rob J and Bethel, Neville and others},
  journal={Science},
  volume={378},
  number={6615},
  pages={49--56},
  year={2022},
  publisher={American Association for the Advancement of Science}
}
```
</details>

<details>
<summary>ESMFold</summary>

```bibtex
@article{lin2023evolutionary,
  title={Evolutionary-scale prediction of atomic-level protein structure with a language model},
  author={Lin, Zeming and Akin, Halil and Rao, Roshan and Hie, Brian and Zhu, Zhongkai and Lu, Wenting and Smetanin, Nikita and Verkuil, Robert and Kabeli, Ori and Shmueli, Yaniv and others},
  journal={Science},
  volume={379},
  number={6637},
  pages={1123--1130},
  year={2023},
  publisher={American Association for the Advancement of Science}
}
```
</details>

<details>
<summary>AlphaFold2</summary>

```bibtex
@article{jumper2021highly,
  title={Highly accurate protein structure prediction with AlphaFold},
  author={Jumper, John and Evans, Richard and Pritzel, Alexander and Green, Tim and Figurnov, Michael and Ronneberger, Olaf and Tunyasuvunakool, Kathryn and Bates, Russ and {\v{Z}}{\'\i}dek, Augustin and Potapenko, Anna and others},
  journal={nature},
  volume={596},
  number={7873},
  pages={583--589},
  year={2021},
  publisher={Nature Publishing Group UK London}
}
```
</details>

## Contributing 

We welcome contributions from the community to help improve the evaluation tool!

📄 Check out the [Contributing Guide](CONTRIBUTING.md) to get started.

✅ Code Quality: 
We use `pre-commit` hooks to ensure consistency and code quality. Please install them before making commits:

```bash
pip install pre-commit
pre-commit install
```

## Code of Conduct

We are committed to fostering a welcoming and inclusive environment.
Please review our [Code of Conduct](CODE_OF_CONDUCT.md) for guidelines on how to participate respectfully.


## Security

If you discover a potential security issue in this project, or think you may
have discovered a security issue, please report it privately to the maintainer at c.liu4@uva.nl.

Please do **not** create a public GitHub issue.

## License

This project is licensed under the [Apache 2.0 License](./LICENSE). It is free for both academic research and commercial use.

