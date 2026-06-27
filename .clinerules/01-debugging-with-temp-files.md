# Debugging & Extraction via Temporary Files

When debugging or extracting information from the codebase, always use the following workflow:

1. **Write** executable/debugging code to a temporary file (e.g., `/tmp/cof_*.py`, `/tmp/cof_*.sh`)
2. **Run** the temporary file via the CLI
3. **Read** the output from the file's stdout
4. **Use** the output to inform next steps
5. **Clean up** each temporary file individually at the **end** of the task

## Rationale
- Keeps debugging code organized and inspectable
- Makes debugging easier since you can review the script
- Prevents accidental side effects from inline commands
- Maintains a clean workspace

### Example Workflow

Instead of:

```bash
# Direct execution ❌
cat somefile.json | python3 -c "import sys, json; print(json.load(sys.stdin)['key'])"
```

I will:

```bash
# 1. Write to temp file
# /tmp/cof_extract_key.py
import sys, json
data = json.load(open("/path/to/file.json"))
print(data['key'])

# 2. Run the file
python3 /tmp/cof_extract_key.py

# 3. Read the output
# (capture it and use it)

# 4. At end of task: delete the temp file
rm /tmp/cof_extract_key.py
```
