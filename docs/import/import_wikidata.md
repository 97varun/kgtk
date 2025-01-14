This command will import a Wikidata dump in json format (compressed in gzip or bz2) into KGTK format,  generating 3 files:

- A nodes file containing all Qnodes and Pnodes in Wikidata
- An edges file containing all the statements in Wikidata
- A qualifiers file containing all qualifiers on statements in Wikidata

## Usage
```
usage: kgtk import-wikidata [-h] [-i INPUT_FILE] [--procs PROCS]
                            [--max-size-per-mapper-queue MAX_SIZE_PER_MAPPER_QUEUE]
                            [--mapper-batch-size MAPPER_BATCH_SIZE]
                            [--single-mapper-queue [True/False]]
                            [--collector-batch-size COLLECTOR_BATCH_SIZE]
                            [--use-shm [True/False]]
                            [--collector-queue-per-proc-size COLLECTOR_QUEUE_PER_PROC_SIZE]
                            [--node NODE_FILE] [--edge MINIMAL_EDGE_FILE]
                            [--qual MINIMAL_QUAL_FILE]
                            [--split-alias-file SPLIT_ALIAS_FILE]
                            [--split-en-alias-file SPLIT_EN_ALIAS_FILE]
                            [--split-datatype-file SPLIT_DATATYPE_FILE]
                            [--split-description-file SPLIT_DESCRIPTION_FILE]
                            [--split-en-description-file SPLIT_EN_DESCRIPTION_FILE]
                            [--split-label-file SPLIT_LABEL_FILE]
                            [--split-en-label-file SPLIT_EN_LABEL_FILE]
                            [--split-reference-file SPLIT_REFERENCE_FILE]
                            [--split-sitelink-file SPLIT_SITELINK_FILE]
                            [--split-en-sitelink-file SPLIT_EN_SITELINK_FILE]
                            [--split-type-file SPLIT_TYPE_FILE]
                            [--split-property-edge-file SPLIT_PROPERTY_EDGE_FILE]
                            [--split-property-qual-file SPLIT_PROPERTY_QUAL_FILE]
                            [--limit LIMIT] [--nth NTH] [--lang LANG]
                            [--source SOURCE] [--deprecated]
                            [--use-python-cat [True/False]]
                            [--interleave [True/False]]
                            [--parse-aliases [True/False]]
                            [--parse-descriptions [True/False]]
                            [--parse-labels [True/False]]
                            [--parse-sitelinks [True/False]]
                            [--parse-claims [True/False]]
                            [--parse-references [True/False]]
                            [--fail-if-missing [True/False]]
                            [--all-languages [True/False]]
                            [--warn-if-missing [True/False]]
                            [--progress-interval PROGRESS_INTERVAL]
                            [--use-mgzip-for-input [True/False]]
                            [--use-mgzip-for-output [True/False]]
                            [--mgzip-threads-for-input MGZIP_THREADS_FOR_INPUT]
                            [--mgzip-threads-for-output MGZIP_THREADS_FOR_OUTPUT]
                            [--value-hash-width VALUE_HASH_WIDTH]
                            [--claim-id-hash-width CLAIM_ID_HASH_WIDTH]
                            [--clean [True/False]]
                            [--clean-verbose [True/False]]
                            [--invalid-edge-file INVALID_EDGE_FILE]
                            [--invalid-qual-file INVALID_QUAL_FILE]
                            [--skip-validation [True/False]]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT_FILE, --input-file INPUT_FILE
                        input path file (may be .bz2) (May be omitted or '-'
                        for stdin.)
  --procs PROCS         number of processes to run in parallel, default 2
  --max-size-per-mapper-queue MAX_SIZE_PER_MAPPER_QUEUE
                        max depth of server queues, default 4
  --mapper-batch-size MAPPER_BATCH_SIZE
                        How many statements to queue in a batch to a worker.
                        (default=5)
  --single-mapper-queue [True/False]
                        If true, use a single queue for worker tasks. If
                        false, each worker has its own task queue.
                        (default=False).
  --collector-batch-size COLLECTOR_BATCH_SIZE
                        How many statements to queue in a batch to the
                        collector. (default=5)
  --use-shm [True/False]
                        If true, use ShmQueue. (default=False).
  --collector-queue-per-proc-size COLLECTOR_QUEUE_PER_PROC_SIZE
                        collector queue depth per proc, default 2
  --node NODE_FILE, --node-file NODE_FILE
                        path to output node file
  --edge MINIMAL_EDGE_FILE, --edge-file MINIMAL_EDGE_FILE, --minimal-edge-file MINIMAL_EDGE_FILE
                        path to output edge file with minimal data
  --qual MINIMAL_QUAL_FILE, --qual-file MINIMAL_QUAL_FILE, --minimal-qual-file MINIMAL_QUAL_FILE
                        path to output qual file with minimal data
  --split-alias-file SPLIT_ALIAS_FILE
                        path to output split alias file
  --split-en-alias-file SPLIT_EN_ALIAS_FILE
                        path to output split English alias file
  --split-datatype-file SPLIT_DATATYPE_FILE
                        path to output split datatype file
  --split-description-file SPLIT_DESCRIPTION_FILE
                        path to output splitdescription file
  --split-en-description-file SPLIT_EN_DESCRIPTION_FILE
                        path to output split English description file
  --split-label-file SPLIT_LABEL_FILE
                        path to output split label file
  --split-en-label-file SPLIT_EN_LABEL_FILE
                        path to output split English label file
  --split-reference-file SPLIT_REFERENCE_FILE
                        path to output split reference file
  --split-sitelink-file SPLIT_SITELINK_FILE
                        path to output split sitelink file
  --split-en-sitelink-file SPLIT_EN_SITELINK_FILE
                        path to output split English sitelink file
  --split-type-file SPLIT_TYPE_FILE, --split-entity-type-file SPLIT_TYPE_FILE
                        path to output split entry type file
  --split-property-edge-file SPLIT_PROPERTY_EDGE_FILE
                        path to output split property edge file
  --split-property-qual-file SPLIT_PROPERTY_QUAL_FILE
                        path to output split property qualifier file
  --limit LIMIT         number of lines of input file to run on, default runs
                        on all
  --nth NTH             Process every nth line, default processes all lines
  --lang LANG           languages to extract, comma separated, default en
  --source SOURCE       wikidata version number, default: wikidata
  --deprecated          option to include deprecated statements, not included
                        by default
  --use-python-cat [True/False]
                        If true, use portable code to combine file fragments.
                        (default=False).
  --interleave [True/False]
                        If true, output the edges and qualifiers in a single
                        file (the edge file). (default=False).
  --parse-aliases [True/False]
                        If true, parse aliases. (default=True).
  --parse-descriptions [True/False]
                        If true, parse descriptions. (default=True).
  --parse-labels [True/False]
                        If true, parse labels. (default=True).
  --parse-sitelinks [True/False]
                        If true, parse sitelinks. (default=True).
  --parse-claims [True/False]
                        If true, parse claims. (default=True).
  --parse-references [True/False]
                        If true, parse references in claims. (default=True).
  --fail-if-missing [True/False]
                        If true, fail if expected data is missing.
                        (default=True).
  --all-languages [True/False]
                        If true, override --lang and import aliases,
                        dscriptions, and labels in all languages.
                        (default=False).
  --warn-if-missing [True/False]
                        If true, print a warning message if expected data is
                        missing. (default=True).
  --progress-interval PROGRESS_INTERVAL
                        How often to report progress. (default=500000)
  --use-mgzip-for-input [True/False]
                        If true, use the multithreaded gzip package, mgzip,
                        for input. (default=False).
  --use-mgzip-for-output [True/False]
                        If true, use the multithreaded gzip package, mgzip,
                        for output. (default=False).
  --mgzip-threads-for-input MGZIP_THREADS_FOR_INPUT
                        The number of threads per mgzip input streama.
                        (default=3).
  --mgzip-threads-for-output MGZIP_THREADS_FOR_OUTPUT
                        The number of threads per mgzip output streama.
                        (default=3).
  --value-hash-width VALUE_HASH_WIDTH
                        How many characters should be used in a value hash?
                        (default=8)
  --claim-id-hash-width CLAIM_ID_HASH_WIDTH
                        How many characters should be used to hash the claim
                        ID? 0 means do not hash the claim ID. (default=0)
  --clean [True/False]  If true, clean the input values before writing it.
                        (default=False).
  --clean-verbose [True/False]
                        If true, give verbose feedback when cleaning input
                        values. (default=False).
  --invalid-edge-file INVALID_EDGE_FILE
                        path to output edges with invalid input values
  --invalid-qual-file INVALID_QUAL_FILE
                        path to output qual edges with invalid input values
  --skip-validation [True/False]
                        If true, skip output record validation.
                        (default=False).
```

### Examples

Import the entire wikidata dump into kgtk format, extracting english labels, descriptions and aliases.

```
kgtk import-wikidata -i wikidata-all-20200504.json.bz2 --node nodefile.tsv --edge edgefile.tsv --qual qualfile.tsv 
```

The following command includes optimizations for running the import process in parallel for English: 

```
kgtk  --debug --timing --progress import-wikidata \
        -i wikidata-all-20200504.json.gz \
        --node nodefile.tsv \
        --edge edgefile.tsv \
        --qual qualfile.tsv \
        --use-mgzip-for-input True \
        --use-mgzip-for-output True \
        --use-shm True \
        --procs 6 \
        --mapper-batch-size 5 \
        --max-size-per-mapper-queue 3 \
        --single-mapper-queue True \
        --collect-results True \
        --collect-seperately True\
        --collector-batch-size 10 \
        --collector-queue-per-proc-size 3 \
        --progress-interval 500000 --fail-if-missing False
```
