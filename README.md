# kgtk

### Installation

0. Our installations will be in a conda environment. If you don't have a conda installed, follow [link](https://docs.conda.io/projects/conda/en/latest/user-guide/install/) to install it.
1. Set up your own conda environment:
```
conda create -n kgtk-env python=3.7
conda activate kgtk-env
```
 **Note:** Installing Graph-tool is problematic on python 3.8 and out of a virtual environment. Thus: **the advised installation path is by using a virtual environment.**

2. Clone this repository: `git clone https://github.com/usc-isi-i2/kgtk.git`
2. `pip install -r requirements.txt`
3. Install `graph-tool`. If you use conda, then you can run `conda install -c conda-forge graph-tool`, else see these [instructions](https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions). 
4. Install `mlr`. Depending on your environment, you can run one of the following:
  * `brew update && brew install miller` (on mac)
  * `sudo port selfupdate && sudo port install miller` (on mac)
  * `sudo apt-get install miller` (linux)
  * `sudo apt install miller` (linux)
  * `sudo yum install miller` (linux)
  
More installation options for `mlr` can be found [here](https://johnkerl.org/miller/doc/build.html).

### The Miller Package

1. Our code uses the "miller" package to manipulate formatted data.

2. TheGitHub repository for miller is:
```
https://github.com/johnkerl/miller
```
3. The documentaton is:
```
https://www.mankier.com/1/mlr
```
4. You may need to install the miller command (mlr) on your system.
   * OpenSUSE Tumbleweed Linux: install package `miller` from Main Repository (OSS)

### List of supported tools
* `instances`
* `reachable_nodes`
* `filter`
* `text_embedding`
* `remove_columns`
* `sort`
* `merge_identical_nodes`
* `zconcat`

To get an information on how to use each of them, run:
`kgtk [TOOL] -h`

More detailed description of the arguments will be added here promptly.

### Developer Instruction

Please refer to [this](README_dev.md)
