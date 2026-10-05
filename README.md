
This repository contains the code for the paper "TAGFuzz: Compiler Directed Fuzzing based on Target Activation Graph"


## Repository layout

```text
TAGFuzz/
├── configs/
│   └── go-fse20.example.yaml   # Example settings
├── scripts/
│   ├── build-instrumented-go.sh
│   ├── go-compile.sh
│   ├── go-coverage-json.sh
│   └── run-smoke.sh
├── tagfuzz/
│   ├── cli.py                 # Command-line entry point
│   ├── config.py              # YAML configuration loading
│   ├── engine.py              # Candidate generation and selection loop
│   ├── tag_graph.py           # Target schema and graph operations
│   ├── activation.py          # Activation state and frontier analysis
│   ├── features.py            # Go source feature extraction
│   ├── prompts.py             # Feedback prompt construction
│   ├── llm.py                 # generators
│   ├── code_extract.py        # Generated Go code extraction
│   ├── compiler.py            # Compiler execution and coverage parsing
│   ├── reward.py              # Activation rewards and relative advantages
│   └── grpo.py                # Training adapter
├── targets/go/fse20.yaml      # 20 target specifications
└── requirements.txt
```
## 1. Build and Configure the Compiler

```bash
bash scripts/build-instrumented-go.sh "$PWD/toolchains/go1.20.6-tagfuzz"
export TAGFUZZ_GOROOT="$PWD/toolchains/go1.20.6-tagfuzz/goroot"
```


## 2. Configure the Model

Modify the two items under `model` in `configs/go-fse20.example.yaml`, while keeping the other configurations unchanged:

```yaml
model:
backend: hf
name: /absolute/path/to/your/model
```

Replace `/absolute/path/to/your/model` with the actual path to your model directory.

## 3. Start the Program

```bash
python -m tagfuzz.cli run configs/go-fse20.example.yaml \
--target ssa_decompose_slice_phi \
--budget-calls 128 \
--work-dir runs/test-001
```

