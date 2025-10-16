# Aria Autoformalizer Agent

## Prerequisites

Before running the agent, you must configure your API credentials in configs/config.yaml.

All commands should be executed from the root directory of the `Aria` project.

## Running on a Single Data Entry

To process a single statement, run the following command in your terminal:

```bash
python -m src.Agents.Flow.run_single
```

## Running on a Batch of Data

To process multiple statements from a `.jsonl` file, use the following command:

```bash
python -m src.Agents.Flow.run_batch data.jsonl
```

### Input File Format

The input .jsonl file must contain entries where each line is a JSON object. Each object must include the following two fields:

`"id"`: A unique identifier for the entry, used for labeling purposes.

`"nl_statement"`: The natural language statement to be formalized.
