from mcp_job_search.lint import lint_cv

result = lint_cv(
    "tests/fixtures/sample_cv_with_violations.html",
    rules_path="config/lint_rules.example.yaml",
)

print(f"lint_cv: {result['html_path'].split('/')[-1]}")
print(f"clean: {result['clean']}\n")
for f in result["findings"]:
    icon = "x" if f["severity"] == "error" else "."
    print(f"  [{icon}] {f['message']}")
