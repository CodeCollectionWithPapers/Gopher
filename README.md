# Gopher

## Introduction
Recent advancements in Large Language Models (LLMs) have demonstrated significant potential in Automated Program Repair (APR). Crucially, the APR performance of LLMs heavily depends on the quality of the input context. However, existing LLM-based APR techniques predominantly employ contexts with fixed granularity (e.g., method-level or class-level), which limits the repair capabilities of LLMs due to information scarcity or noise interference. Moreover, a prevalent input formulation involves presenting LLMs with the entire buggy method and prompting them to generate a fully corrected version. This approach risks introducing redundant or even detrimental code modifications that exceed the necessary scope of the repair. In this paper, we propose **Gopher**, a novel context-driven APR approach. The results show that **Gopher** can repair 179 bugs with perfect defect localization on Defects4J, outperforming SOTA baselines by 9.8% to 79%. Compared to the studied LLMs directly generating patches, **Gopher** achieves an average improvement of 21.4% in correct repairs across all models on Defects4J. Our study demonstrates the effectiveness of the proposed context refinement method in improving APR performance. 
## Project Structure
```text
├─📁 Gopher--------------- # Gopher's core code modules
│ ├─📁 analysis
│ ├─📁 core
│ ├─📁 execution
│ ├─📁 LLM
│ ├─📁 prompting
│ ├─📁 test_artifact
│ ├─📄 init.py
│ └─📄 workflow.py
├─📁 configs-------------- # Configuration directory
├─📁 result--------------- # Experimental results
│ ├─📁 RQ1
│ ├─📁 RQ2
│ ├─📁 RQ3
│ ├─📁 RQ4
│ └─📁 RWB
├─📁 scripts-------------- # Data preprocessing
├─📄 main_generator.py
└─📄 requirements.txt
```
## How to run

### Environmental Requirement
1. **OS**: Ubuntu 22.04.5 LTS <br>
2. **RAM**: 100GB+ for processing large CPG <br>
3. **Python**: 3.9 <br>
4. **Java**: JDK11 and 17 <br>
5. **Docker**: Must be installed and running for the Defects4J sandbox <br>
6. **Joern**: v4.0.263 <br> 

### Installation

```bash 
git clone https://github.com/CodeCollectionWithPapers/Gopher.git
cd Gopher
pip install -r requirements.txt
 ```
Run the automated script to install Joern and its dependencies. Alternatively, install manually from [Joern](https://github.com/joernio/joern).
```bash 
bash scripts/install_joern.sh
 ```
> After installation, ensure that `joern.installation_path` in `configs/settings.yaml` points to the correct installation directory (default: `/opt/joern/joern-cli`).

### Data Preparation
1. Clone [Defects4J](https://github.com/rjust/defects4j)
2. Setup Defects4J following [README](https://github.com/rjust/defects4j/blob/master/README.md)
3. Checkout Installation <br>
```bash defects4j checkout -p Lang -v 1b -w /workspace/lang_1_buggy ```
4. Use a preprocessing script to extract bug information, such as the top 5 bugs for Chart items.
```bash
python scripts/preprocess_D4J.py \
   --output_dir ./your_data_input \
   --project Chart \
   --ids 1-5
```
5. Prepare Dataset [QuixBugs](https://github.com/jkoppel/QuixBugs) <br>
6. Prepare Dataset [Minecraft](https://github.com/SET-IITGN/Minecraft) <br>
7. Prepare Dataset [RWB](https://huggingface.co/datasets/anonymity0001/RWB/tree/main)
> Please note that our experimental baselines can be downloaded from [Baselines](https://huggingface.co/datasets/anonymity0001/Gopher_baselines/tree/main).
### Run
```bash
python main_generator.py
```

