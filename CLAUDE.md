# Claude Coding Rules

## Overview
This document contains coding standards and best practices that must be followed for all code development. These rules prioritize maintainability, simplicity, and modern Python development practices.

## Core Principles
- Write code with minimal complexity for maximum maintainability and clarity
- Choose simple, readable solutions over clever or complex implementations
- Prioritize code that any team member can confidently understand, modify, and debug

## Pull Request Evaluation

When evaluating pull requests for merge, adopt the **Merge Specialist** persona defined in [TEAM.md](TEAM.md). This persona provides comprehensive guidelines for:

- Running and verifying tests
- Assessing code quality against these standards
- Reviewing architecture and design decisions
- Checking for breaking changes
- Evaluating performance impact
- Ensuring documentation is complete

**IMPORTANT**: Before approving any PR for merge, the Merge Specialist must verify that all tests pass and no existing functionality is broken. A PR with failing tests should NEVER be approved for merge.

## Technology Stack

### Package Management
- Always use `uv` and `pyproject.toml` for package management
- Never use `pip` directly

### Modern Python Libraries
- **Data Processing**: Use `polars` instead of `pandas`
- **Web APIs**: Use `fastapi` instead of `flask`
- **Code Formatting/Linting**: Use `ruff` for both linting and formatting
- **Type Checking**: Use `mypy` - type checks have become actually useful and should be part of CI/CD
- **Performance**: Leverage modern CPython improvements - CPython is now much faster

## Code Style Guidelines

### Function Structure
- All internal/private functions must start with an underscore (`_`)
- Private functions should be placed at the top of the file, followed by public functions
- Functions should be modular, containing no more than 30-50 lines
- Use two blank lines between function definitions
- One function parameter per line for better readability

### Type Annotations
- Use clear type annotations for all function parameters
- One function parameter per line for better readability
- Example:
  ```python
  def process_data(
      input_file: str,
      output_format: str,
      validate: bool = True
  ) -> dict:
      pass
  ```

### Type Hints for Optional Parameters
- Always use `Optional[type]` for parameters that can be None
- Be explicit about optional parameters, especially when they have special meanings:
  ```python
  from typing import Optional, List
  
  def process_samples(
      sample_size: Optional[int] = None,  # None means use default
      language: Optional[str] = None      # None means no filtering
  ) -> List[dict]:
      """Process dataset samples.
      
      Args:
          sample_size: Number of samples. None uses default, 0 means all.
          language: Language filter. None means all languages.
      """
      if sample_size == 0:
          # Special case: process all samples
          return process_all()
      elif sample_size is None:
          # Use default sample size
          sample_size = DEFAULT_SAMPLE_SIZE
          
      # Process with explicit sample size
      return process_with_size(sample_size)
  ```

### Class Definitions with Pydantic
- Consider using Pydantic BaseModel for all class definitions to leverage validation, serialization, and other powerful features
- Pydantic provides automatic validation, type coercion, and serialization capabilities
- Example:
  ```python
  from pydantic import BaseModel, Field, validator
  from typing import Optional
  
  class UserConfig(BaseModel):
      """User configuration settings."""
      
      username: str = Field(..., min_length=3, max_length=50)
      email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
      timeout_seconds: int = Field(default=30, ge=1, le=300)
      debug_enabled: bool = False
      
      @validator('username')
      def username_alphanumeric(cls, v: str) -> str:
          if not v.replace('_', '').isalnum():
              raise ValueError('Username must be alphanumeric')
          return v.lower()
  ```

### Main Function Pattern
- The main function should act as a control flow orchestrator
- Parse command line arguments and delegate to other functions
- Avoid implementing business logic directly in main()

### Command-Line Interface Design
When creating CLI applications:

1. **Use argparse with comprehensive help**:
   ```python
   parser = argparse.ArgumentParser(
       description="Clear description of what the tool does",
       formatter_class=argparse.RawDescriptionHelpFormatter,
       epilog="""
   Example usage:
       # Basic usage
       uv run python -m module --param value
       
       # With environment variable
       export PARAM=value
       uv run python -m module
   """
   )
   ```

2. **Support both CLI args and environment variables**:
   ```python
   def _get_config_value(cli_value: Optional[str] = None) -> str:
       if cli_value:
           return cli_value
       
       env_value = os.getenv("CONFIG_VAR")
       if env_value:
           return env_value
       
       raise ValueError("Value must be provided via --param or CONFIG_VAR env var")
   ```

3. **Provide sensible defaults**:
   ```python
   parser.add_argument(
       "--sample-size",
       type=int,
       help=f"Number of samples (default: {DEFAULT_SIZE}). Use 0 for all",
   )
   ```

4. **Use special values for "all" options**:
   ```python
   if sample_size == 0 or sample_size is None:
       # Process entire dataset
   else:
       # Process sample
   ```

### Imports
- Write imports as multi-line imports for better readability
- Example:
  ```python
  from .services.output_formatter import (
      _display_evaluation_results,
      _print_results_summary,
      _check_mcp_generation_criteria
  )
  ```

### Constants
- Don't hard code constants within functions
- For trivial constants, declare them at the top of the file:
  ```python
  STARTUP_DELAY: int = 10
  MAX_RETRIES: int = 3
  ```
- For many constants, create a separate `constants.py` file with a class structure

### Logging Configuration
- Always use the following logging configuration:
  ```python
  import logging
  
  # Configure logging with basicConfig
  logging.basicConfig(
      level=logging.INFO,  # Set the log level to INFO
      # Define log message format
      format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
  )
  ```

### Logging Best Practices
- Add sufficient log messages throughout the code to aid in debugging and monitoring
- Don't shy away from adding debug logs using `logging.debug()` for detailed tracing
- When printing a dictionary as part of a trace message, always pretty print it:
  ```python
  logger.info(f"Processing data:\n{json.dumps(data_dict, indent=2, default=str)}")
  ```
- Consider adding a `--debug` flag to the application that sets the logging level to DEBUG:
  ```python
  if args.debug:
      logging.getLogger().setLevel(logging.DEBUG)
  ```

### Performance Feedback
Provide users with feedback on long-running operations:

1. **Display elapsed time after completion**:
   ```python
   start_time = time.time()
   # ... perform operation ...
   elapsed_time = time.time() - start_time
   minutes = int(elapsed_time // 60)
   seconds = elapsed_time % 60
   
   if minutes > 0:
       logger.info(f"Completed in {minutes} minutes and {seconds:.1f} seconds")
   else:
       logger.info(f"Completed in {seconds:.1f} seconds")
   ```

2. **Warn about potentially long operations**:
   ```python
   if processing_full_dataset:
       logger.warning("Processing FULL dataset. This may take a long time.")
   else:
       logger.info(f"Processing {sample_size} samples.")
   ```

3. **Show configuration at startup**:
   ```python
   logger.info(f"Configuration: {config.model_dump()}")
   ```

### Performance Optimization
- Use `@lru_cache` decorator where appropriate for expensive computations

### External Resource Management
When working with external data sources (APIs, datasets, databases):

1. **Version/pin external dependencies**:
   ```python
   # Specify exact versions or commits for reproducibility
   API_VERSION = "v2"
   SCHEMA_VERSION = "2024-01-15"
   ```

2. **Document external resources in code**:
   ```python
   # Constants file with clear documentation
   DATA_SOURCE: str = "source-name"  # Documentation URL: https://...
   API_ENDPOINT: str = "https://api.example.com/v1"  # API docs: https://...
   ```

3. **Handle data filtering and edge cases gracefully**:
   ```python
   def load_filtered_data(
       filters: Dict[str, Any],
       limit: Optional[int] = None
   ) -> List[dict]:
       data = fetch_from_source()
       
       # Apply filters with clear feedback
       for key, value in filters.items():
           filtered = [item for item in data if item.get(key) == value]
           logger.info(f"Filter '{key}={value}': {len(data)} -> {len(filtered)} items")
           data = filtered
       
       if not data:
           raise ValueError(f"No data found matching filters: {filters}")
       
       # Handle size limits
       if limit and len(data) < limit:
           logger.warning(f"Only {len(data)} items available (requested: {limit})")
           
       return data[:limit] if limit else data
   ```

4. **Provide actionable error messages**:
   ```python
   if not data:
       raise ValueError(
           f"No data retrieved from {DATA_SOURCE}. "
           f"Check connection and credentials. "
           f"Documentation: {DOCS_URL}"
       )
   ```

### Decorators and Functional Patterns

#### Guidelines for Using Decorators and Functional Patterns Appropriately

**Use Decorators When:**
- They're built-in or widely known (`@property`, `@staticmethod`, `@dataclass`)
- They have a single, clear purpose (`@login_required`, `@cache`)
- They don't change function behavior dramatically

Example - Good use of decorators:
```python
# Good - clear, single purpose
@dataclass
class User:
    name: str
    email: str

@lru_cache(maxsize=128)
def expensive_calculation(n: int) -> int:
    return sum(i**2 for i in range(n))
```

**Use Functional Patterns When:**
- Simple transformations are clearer than loops
- You need pure functions for testing
- The functional approach is more readable

Example - Good use of functional patterns:
```python
# Good - simple and clear
numbers = [1, 2, 3, 4, 5]
squared = [n**2 for n in numbers]
evens = [n for n in numbers if n % 2 == 0]

# Good - simple map operation
names = ["alice", "bob", "charlie"]
capitalized = list(map(str.capitalize, names))
```

**Avoid When:**
- You're chaining multiple complex operations
- The code requires explaining how it works
- An entry-level developer would struggle to modify it
- You're using advanced functional programming concepts

Example - Avoid complex patterns:
```python
# Bad - too complex, hard to understand
result = reduce(lambda x, y: x + y, 
                filter(lambda x: x % 2 == 0,
                       map(lambda x: x**2, range(10))))

# Good - clear and simple
total = 0
for i in range(10):
    squared = i ** 2
    if squared % 2 == 0:
        total += squared
```

#### Avoid Deep Nesting
- Limit nesting to 2-3 levels maximum
- Extract nested logic into well-named functions
- Use early returns to reduce nesting

Example - Reducing nesting:
```python
# Bad - too much nesting
def process_data(data):
    if data:
        if data.get("users"):
            for user in data["users"]:
                if user.get("active"):
                    if user.get("email"):
                        send_email(user["email"])

# Good - reduced nesting with early returns
def process_data(data):
    if not data:
        return
    
    users = data.get("users", [])
    if not users:
        return
    
    for user in users:
        _process_active_user(user)

def _process_active_user(user):
    if not user.get("active"):
        return
    
    email = user.get("email")
    if email:
        send_email(email)
```

### Code Validation
- Always run `uv run python -m py_compile <filename>` after making changes to Python files
- Always run `bash -n <filename>` after making changes to bash/shell scripts to check syntax

## Error Handling and Exceptions

### Exception Handling Principles
- Use specific exception types, avoid bare `except:` clauses
- Always log exceptions with proper context
- Fail fast and fail clearly - don't suppress errors silently
- Use custom exceptions for domain-specific errors

### Exception Pattern
```python
import logging

logger = logging.getLogger(__name__)

class DomainSpecificError(Exception):
    """Base exception for our application"""
    pass

def process_data(data: dict) -> dict:
    try:
        # Process data
        result = _validate_and_transform(data)
        return result
    except ValidationError as e:
        logger.error(f"Validation failed for data: {e}")
        raise DomainSpecificError(f"Invalid input data: {e}") from e
    except Exception as e:
        logger.exception("Unexpected error in process_data")
        raise
```

### Error Messages
- Write clear, actionable error messages
- Include context about what was being attempted
- Suggest possible solutions when appropriate

## Testing Standards

### Testing Framework
- Use `pytest` as the primary testing framework
- Maintain minimum 80% code coverage
- Use `pytest-cov` for coverage reporting

### Test Structure
```python
import pytest
from unittest.mock import Mock, patch

class TestFeatureName:
    """Tests for feature_name module"""
    
    def test_happy_path(self):
        """Test normal operation with valid inputs"""
        # Arrange
        input_data = {"key": "value"}
        
        # Act
        result = function_under_test(input_data)
        
        # Assert
        assert result["status"] == "success"
    
    def test_edge_case(self):
        """Test boundary conditions"""
        pass
    
    def test_error_handling(self):
        """Test error scenarios"""
        with pytest.raises(ValueError, match="Invalid input"):
            function_under_test(None)
```

### Testing Best Practices
- Follow AAA pattern: Arrange, Act, Assert
- One assertion per test when possible
- Use descriptive test names that explain what is being tested
- Mock external dependencies
- Use fixtures for common test data
- Test both happy paths and error cases

### Running Tests Before Pull Requests

**CRITICAL**: Always run the full test suite before submitting a pull request or after completing a major feature.

#### When to Run Tests
1. **Before submitting a pull request**: All tests must pass before creating a PR
2. **After completing a major feature**: Verify no regressions were introduced
3. **After making significant refactoring changes**: Ensure existing functionality still works
4. **After updating dependencies**: Verify compatibility with new versions

#### How to Run Tests
Run the complete test suite with parallel execution:

```bash
# Run all tests in parallel (using 8 workers)
uv run pytest tests/ -n 8

# Expected output (as of 2026-01-06):
# - 701 passed
# - 57 skipped
# - Coverage: ~39.50%
# - Execution time: ~30 seconds
```

#### Test Execution Options
```bash
# Run tests serially (slower, but uses less memory)
uv run pytest tests/

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run with verbose output
uv run pytest tests/ -n 8 -v

# Run and stop at first failure
uv run pytest tests/ -n 8 -x

# Run with coverage report
uv run pytest tests/ -n 8 --cov=registry --cov-report=term-missing
```

#### Test Prerequisites
Before running tests, ensure:

1. **MongoDB is running** (for integration tests):
   ```bash
   docker ps | grep mongo
   # Should show: mcp-mongodb running on 0.0.0.0:27017
   ```

2. **Test environment is configured**:
   - Tests automatically set `DOCUMENTDB_HOST=localhost`
   - Tests use `mongodb-ce` storage backend
   - Tests use `directConnection=true` for single-node MongoDB

#### Continuous Integration
Tests run automatically via GitHub Actions when:
- Pull requests are created targeting `main` or `develop` branches
- Code is pushed to `main` or `develop` branches

See [.github/workflows/registry-test.yml](.github/workflows/registry-test.yml:7-8) for CI configuration.

#### Acceptable Test Results
- **All unit tests must pass** (no failures allowed in unit tests)
- **Integration tests**: Some tests may be skipped due to known issues
- **Coverage**: Minimum 35% coverage required (configured in pyproject.toml:87)
- **Warnings**: Minor warnings are acceptable, but investigate new warnings

#### What to Do If Tests Fail
1. Review the test failure output carefully
2. Fix the failing test(s) before submitting PR
3. Re-run tests to verify the fix
4. Never submit a PR with failing tests
5. If a test failure is unrelated to your changes, investigate and fix it or document why it should be skipped

## Async/Await Best Practices

### Async Code Structure
```python
import asyncio
from typing import List

async def fetch_data(url: str) -> dict:
    """Fetch data from URL asynchronously"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

async def process_urls(urls: List[str]) -> List[dict]:
    """Process multiple URLs concurrently"""
    tasks = [fetch_data(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### Async Guidelines
- Use `async with` for async context managers
- Use `asyncio.gather()` for concurrent operations
- Handle exceptions in async code properly
- Don't mix blocking and async code
- Use `asyncio.run()` to run async functions from sync code

## Documentation Standards

### Docstring Format
Use Google-style docstrings:
```python
def calculate_metrics(
    data: List[float],
    threshold: float = 0.5
) -> Dict[str, float]:
    """Calculate statistical metrics for the given data.
    
    Args:
        data: List of numerical values to analyze
        threshold: Minimum value to include in calculations
        
    Returns:
        Dictionary containing calculated metrics:
        - mean: Average value
        - std: Standard deviation
        - count: Number of values above threshold
        
    Raises:
        ValueError: If data is empty or contains non-numeric values
        
    Example:
        >>> metrics = calculate_metrics([1.0, 2.0, 3.0])
        >>> print(metrics['mean'])
        2.0
    """
    pass
```

### Documentation Requirements
- All public functions must have docstrings
- Include type hints in function signatures
- Document exceptions that can be raised
- Provide usage examples for complex functions
- Keep docstrings up-to-date with code changes

## Security Guidelines

### Input Validation
- Always validate and sanitize user inputs
- Use Pydantic models for request/response validation
- Never trust external data

### Secrets Management
```python
import os
from typing import Optional

def get_secret(key: str, default: Optional[str] = None) -> str:
    """Retrieve secret from environment variable.
    
    Never hardcode secrets in source code.
    """
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"Required secret '{key}' not found in environment")
    return value
```

### Security Best Practices
- Never log sensitive information (passwords, tokens, PII)
- Use environment variables for configuration
- Validate all inputs, especially from external sources
- Use parameterized queries for database operations
- Keep dependencies updated for security patches

### Security Scanning with Bandit
- Run Bandit regularly as part of the development workflow
- Handle false positives with `# nosec` comments and clear justification
- Common patterns to handle:
  ```python
  # When using random for ML reproducibility (not cryptography)
  # This is not for security/cryptographic purposes - nosec B311
  random.seed(random_seed)
  samples = random.sample(dataset, size)  # nosec B311
  
  # When loading from trusted sources with version pinning
  # This is acceptable for evaluation tools using well-known datasets - nosec B615
  ds = load_dataset(DATASET_NAME, revision="main")  # nosec B615
  ```
- Run security scans with: `uv run bandit -r src/`

### Server Binding Security
- When starting a server, never bind it to `0.0.0.0` unless absolutely necessary
- Prefer binding to `127.0.0.1` for local-only access
- If external access is needed, bind to the specific private IP address:
  ```python
  # Bad - exposes to all interfaces
  app.run(host="0.0.0.0", port=8000)
  
  # Good - local only
  app.run(host="127.0.0.1", port=8000)
  
  # Good - specific private IP
  import socket
  private_ip = socket.gethostbyname(socket.gethostname())
  app.run(host=private_ip, port=8000)
  ```

### Subprocess Security Guidelines

When using the `subprocess` module, follow these security patterns to prevent Bandit B603/B607 findings and avoid shell injection vulnerabilities.

#### ✅ ALWAYS Use List Form (Not String Commands)

```python
# Good - list form prevents shell injection
result = subprocess.run(
    ["nginx", "-s", "reload"],
    capture_output=True,
    text=True,
    timeout=5,
)

# Bad - string form with shell=True is vulnerable to injection
result = subprocess.run("nginx -s reload", shell=True)  # NEVER DO THIS
```

#### ✅ ALWAYS Add Timeout

```python
# Good - prevents DoS from hanging processes
result = subprocess.run(cmd, timeout=30, capture_output=True)

# Bad - no timeout can cause infinite hangs
result = subprocess.run(cmd, capture_output=True)  # Missing timeout!
```

#### ✅ ALWAYS Handle Errors

```python
# Good - proper error handling
try:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,  # Raises CalledProcessError on non-zero exit
        timeout=30,
    )
except subprocess.TimeoutExpired:
    logger.error("Command timed out")
    return False
except subprocess.CalledProcessError as e:
    logger.error(f"Command failed: {e.stderr}")
    return False
```

#### ✅ Approved Subprocess Patterns

**Pattern 1: System Utilities (hardcoded commands)**
```python
# System commands with hardcoded paths and flags
result = subprocess.run(
    ["nginx", "-t"],  # nosec B603 B607 - hardcoded command
    capture_output=True,
    text=True,
    timeout=5,
)

result = subprocess.run(
    ["hostname", "-I"],  # nosec B603 B607 - hardcoded command
    capture_output=True,
    text=True,
    timeout=2,
)
```

**Pattern 2: Internal Scripts (controlled paths)**
```python
# Internal scripts with validated arguments
script_path = os.path.join(project_root, "scripts/generate_token.sh")
result = subprocess.run(
    [script_path, validated_arg],  # nosec B603 - hardcoded internal script path
    capture_output=True,
    text=True,
    timeout=30,
    cwd=working_directory,
)
```

**Pattern 3: External Tools (hardcoded flags, data as arguments)**
```python
# External tools with hardcoded flags - user data passed as arguments, not commands
cmd = ["mcp-scanner", "--format", "json", "--url", user_provided_url]
result = subprocess.run(  # nosec B603 - args are hardcoded flags passed to mcp-scanner tool
    cmd,
    capture_output=True,
    text=True,
    check=True,
    timeout=60,
)
```

#### ✅ Security Comment Standards for Subprocess

When suppressing Bandit warnings for subprocess calls, **always include a clear justification**:

```python
# Good - explains why it's safe
subprocess.run(
    ["nginx", "-s", "reload"],
    ...
)  # nosec B603 B607 - hardcoded command

# Good - explains the security model
subprocess.run(
    [script_path, arg],
    ...
)  # nosec B603 - hardcoded internal script path

# Good - explains what's hardcoded
subprocess.run(
    cmd,
    ...
)  # nosec B603 - args are hardcoded flags passed to tool

# Bad - no justification
subprocess.run(cmd, ...)  # nosec B603
```

**Valid Justification Templates:**
- `# nosec B603 B607 - hardcoded command` - for system utilities (nginx, hostname, etc.)
- `# nosec B603 - hardcoded internal script path` - for internal project scripts
- `# nosec B603 - hardcoded internal script path and flags` - when both path and flags are hardcoded
- `# nosec B603 - args are hardcoded flags passed to [tool-name]` - for external tools

#### ❌ NEVER Do These With Subprocess

```python
# NEVER use shell=True with any user input
user_cmd = f"tool --arg {user_input}"
subprocess.run(user_cmd, shell=True)  # VULNERABLE TO INJECTION

# NEVER construct commands from user input
cmd = f"grep {user_search_term} file.txt"  # VULNERABLE
subprocess.run(cmd, shell=True)

# NEVER skip timeout - can hang forever
subprocess.run(["long-running-command"])  # NO TIMEOUT

# NEVER ignore errors without logging
result = subprocess.run(cmd, capture_output=True)
# No error handling - failures go unnoticed
```

### SQL Security Guidelines

When working with databases, follow these patterns to prevent SQL injection vulnerabilities (Bandit B608).

#### ✅ ALWAYS Use Parameterized Queries

```python
# Good - parameterized query with placeholders
cutoff = datetime.now().isoformat()
query = "DELETE FROM table_name WHERE created_at < ?"
cursor.execute(query, (cutoff,))

# Bad - string formatting is vulnerable to SQL injection
cutoff_str = f"'{datetime.now().isoformat()}'"
query = f"DELETE FROM table_name WHERE created_at < {cutoff_str}"  # VULNERABLE
cursor.execute(query)
```

#### ✅ Validate Identifiers Against Allowlists

For table names and column names that cannot be parameterized, use allowlist validation:

```python
# Define allowlists for table and column names
ALLOWED_TABLES = {"users", "metrics", "auth_logs"}
ALLOWED_COLUMNS = {"created_at", "updated_at", "timestamp"}

def validate_table_name(table: str) -> str:
    """Validate table name against allowlist."""
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table: {table}")
    return table

def validate_column_name(column: str) -> str:
    """Validate column name against allowlist."""
    if column not in ALLOWED_COLUMNS:
        raise ValueError(f"Invalid column: {column}")
    return column

# Use validated identifiers with nosec comment
table = validate_table_name(user_provided_table)
column = validate_column_name(user_provided_column)
query = f"SELECT * FROM {table} WHERE {column} = ?"  # nosec B608 - table and column validated against allowlists
cursor.execute(query, (value,))
```

#### ✅ Return Query and Parameters as Tuple

For query-building methods, return both query string and parameters:

```python
def get_cleanup_query(
    table_name: str,
    days: int
) -> tuple[str, tuple]:
    """Get cleanup query and parameters.

    Returns:
        Tuple of (query_string, parameters)
    """
    # Validate table name against allowlist
    table_name = validate_table_name(table_name)

    # Calculate cutoff date
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    # Build parameterized query
    query = f"DELETE FROM {table_name} WHERE created_at < ?"  # nosec B608 - table_name validated against allowlist

    return query, (cutoff,)

# Use the query and parameters
query, params = get_cleanup_query("metrics", 90)
cursor.execute(query, params)
```

#### ✅ Security Comment Standards for SQL

When suppressing B608 warnings, **always document the validation**:

```python
# Good - documents allowlist validation
query = f"SELECT * FROM {table}"  # nosec B608 - table name validated against allowlist
cursor.execute(query, params)

# Good - references validation function
query = f"DELETE FROM {table}"  # nosec B608 - table validated by validate_table_name()
cursor.execute(query, params)

# Good - explains multiple validations
query = f"SELECT {column} FROM {table}"  # nosec B608 - table and column validated against allowlists
cursor.execute(query, params)

# Bad - no justification
query = f"SELECT * FROM {table}"  # nosec B608
cursor.execute(query)
```

**Valid Justification Templates:**
- `# nosec B608 - table name validated against allowlist`
- `# nosec B608 - column name validated against allowlist`
- `# nosec B608 - table and column validated against allowlists`
- `# nosec B608 - identifier validated by _validate_identifier()`

#### ❌ NEVER Do These With SQL

```python
# NEVER use string formatting for values
value = user_input
query = f"SELECT * FROM users WHERE name = '{value}'"  # VULNERABLE TO SQL INJECTION
cursor.execute(query)

# NEVER concatenate user input into queries
query = "SELECT * FROM " + user_table + " WHERE id = " + user_id  # VULNERABLE
cursor.execute(query)

# NEVER skip validation for identifiers
table = request.args.get('table')  # No validation!
query = f"SELECT * FROM {table}"  # VULNERABLE
cursor.execute(query)

# NEVER use datetime() SQL functions with interpolated values
days = user_input
query = f"DELETE FROM t WHERE created_at < datetime('now', '-{days} days')"  # VULNERABLE
cursor.execute(query)
```

### Security Checklist for Code Review

When reviewing code with subprocess or SQL operations, verify:

**Subprocess Checklist:**
- [ ] Using list form (not string commands)
- [ ] No `shell=True` anywhere
- [ ] Timeout specified
- [ ] Error handling includes `TimeoutExpired` and `CalledProcessError`
- [ ] Commands are hardcoded (no dynamic construction from user input)
- [ ] `# nosec` comments include clear justifications
- [ ] Arguments passed as list elements (not interpolated into commands)

**SQL Checklist:**
- [ ] Using parameterized queries for all values
- [ ] Table and column names validated against allowlists
- [ ] No string formatting or concatenation for SQL values
- [ ] Query methods return `tuple[str, tuple]`
- [ ] `# nosec` comments document validation method
- [ ] No datetime() SQL functions with interpolated parameters

## Development Workflow

### Recommended Development Tools
- **Ruff**: For linting and formatting (replaces multiple tools like isort and many flake8 plugins)
- **Bandit**: For security vulnerability scanning
- **MyPy**: For type checking
- **Pytest**: For testing

### Pre-commit Workflow
Before committing code, run these checks in order:

```bash
# 1. Format and lint with auto-fixes
uv run ruff check --fix . && uv run ruff format .

# 2. Security scanning
uv run bandit -r src/

# 3. Type checking
uv run mypy src/

# 4. Run tests
uv run pytest

# Or run all checks in one command:
uv run ruff check --fix . && uv run ruff format . && uv run bandit -r src/ && uv run mypy src/ && uv run pytest
```

### Adding Development Dependencies
```bash
# Add development dependencies
uv add --dev ruff mypy bandit pytest pytest-cov
```

## Dependency Management

### Project Configuration
Always specify Python version in `pyproject.toml` to avoid warnings:
```toml
[project]
name = "project-name"
version = "0.1.0"
description = "Project description"
requires-python = ">=3.11"  # Always specify this!
dependencies = [
    # ... dependencies
]
```

### Version Pinning
In `pyproject.toml`:
```toml
[project]
dependencies = [
    "fastapi>=0.100.0,<0.200.0",  # Minor version flexibility
    "pydantic==2.5.0",  # Exact version for critical dependencies
    "polars>=0.19.0",  # Minimum version only
]

[tool.uv]
dev-dependencies = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
    "bandit>=1.7.0",
]
```

### Dependency Guidelines
- Pin exact versions for critical dependencies
- Use version ranges for stable libraries
- Separate dev dependencies from runtime dependencies
- Regularly update dependencies for security patches
- Document why specific versions are pinned

## Project Structure

### Standard Layout
```
project_name/
├── src/
│   └── project_name/
│       ├── __init__.py
│       ├── main.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── domain.py
│       ├── services/
│       │   ├── __init__.py
│       │   └── business_logic.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── endpoints.py
│       └── utils/
│           ├── __init__.py
│           └── helpers.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── scripts/
│   └── deploy.sh
├── docs/
├── pyproject.toml
├── README.md
└── .env.example
```

### Module Organization
- Keep related functionality together
- Use clear, descriptive module names
- Avoid circular imports
- Keep modules focused on a single responsibility

### Comprehensive .gitignore
Ensure your `.gitignore` includes all necessary entries:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
dist/
*.egg-info/
*.egg

# Virtual environments
.env
.venv
env/
venv/
ENV/

# Testing and linting caches
.ruff_cache/
.mypy_cache/
.pytest_cache/
.coverage
htmlcov/

# Security reports
bandit_report.json

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Project specific
*.csv  # Or specific output files
.scratchpad/
logs/
output/

# AWS
.aws/
```

## Scratchpad for Planning & Design

The `.scratchpad/` folder contains intermediate and temporary documents used during development that are not meant for long-term storage or committed to the repository.

**Contents:**
- Design discussions and architecture sketches
- Todo lists and task planning documents
- GitHub issue creation planning
- LinkedIn posts and social media drafts
- Session notes and decision logs
- Meeting minutes and action items
- Prototype diagrams and brainstorming documents
- Any other context-specific content created during active work

**Important:**
- `.scratchpad/` is in `.gitignore` and will NOT be committed
- These files are temporary and may be deleted at any time
- Only relevant within the context of current work sessions
- Not suitable for documentation or long-term reference
- Use for active planning, not for finalized documentation

**Naming Convention:**
- Design files: `design-feature-name.md` or `design-YYYY-MM-DD.md`
- Planning files: `plan-feature-name.md` or `task-status.md`
- Drafts: `draft-linkedin-post.md`, `draft-github-issue.md`
- Notes: `session-notes-YYYY-MM-DD.md`, `meeting-minutes.md`
- Sub-tasks: `sub-tasks-issue-NUMBER-feature-name.md`

## Environment Configuration

### Environment Variables
```python
from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    app_name: str = "MyApp"
    debug: bool = False
    database_url: str
    api_key: str
    redis_url: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Global settings instance
settings = Settings()
```

### Configuration Best Practices
- Use Pydantic Settings for type-safe configuration
- Provide `.env.example` with all required variables
- Never commit `.env` files to version control
- Document all environment variables
- Use sensible defaults where appropriate

## Data Validation with Pydantic

### Model Definition
```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class UserRequest(BaseModel):
    """User creation request model."""
    
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: Optional[int] = Field(None, ge=0, le=150)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('username')
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace('_', '').isalnum():
            raise ValueError('Username must be alphanumeric')
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "age": 25
            }
        }
```

### Validation Guidelines
- Use Pydantic for all API request/response models
- Define clear validation rules with Field()
- Use custom validators for complex logic
- Provide examples in model configuration
- Return validation errors with clear messages

## Platform Naming
- Always refer to the service as "Amazon Bedrock" (never "AWS Bedrock")

## GitHub Commit and Pull Request Guidelines
- Never include auto-generated messages like "🤖 Generated with [Claude Code]"
- Never include "Co-Authored-By: Claude <noreply@anthropic.com>"
- Keep commit messages clean and professional
- When creating pull requests, do not include Claude Code attribution or generation messages
- Pull request descriptions should be professional and focus on the technical changes

## Documentation Guidelines
- Never add emojis to README.md files in repositories
- Keep README files professional and emoji-free

### Emoji Usage Guidelines
- **Code**: Absolutely no emojis in source code, comments, or docstrings
- **Documentation**: Avoid emojis in all documentation files (.md, .rst, etc.)
- **Log Messages**: Use plain text only for log messages - no emojis
- **Shell Scripts**: Avoid emojis in shell scripts - prefer plain text status messages
- **Comments**: Use clear, descriptive text instead of emojis in code comments

**Rationale**: Emojis can cause encoding issues, reduce accessibility, appear unprofessional in enterprise environments, and may not render consistently across different systems and terminals.

### README Best Practices
A well-structured README should include:

1. **Prerequisites Section**: List external dependencies and setup requirements
   ```markdown
   ## Prerequisites
   - Python 3.11+
   - AWS credentials configured
   - Amazon Bedrock Guardrail with sensitive information filters
   ```

2. **Links to External Resources**: Provide links to datasets, documentation, and services
   ```markdown
   - Evaluate performance on the [dataset-name](https://link-to-dataset)
   - See [AWS documentation](https://docs.aws.amazon.com/...) for setup
   ```

3. **Clear Command Examples**: Show all command-line options with examples
   ```markdown
   ## Usage
   # Basic usage
   uv run python -m module_name --required-param value
   
   # With all options
   uv run python -m module_name --param1 value1 --param2 value2
   
   # Using environment variables
   export CONFIG_VAR=value
   uv run python -m module_name
   ```

4. **Development Workflow**: Include a section on development practices
   ```markdown
   ## Development Workflow
   # Run all checks before committing
   uv run ruff check --fix . && uv run ruff format . && uv run bandit -r src/
   ```

5. **Performance Warnings**: Alert users about time-intensive operations
   ```markdown
   # Evaluate full dataset (warning: this may take a long time)
   uv run python -m module_name --sample-size 0
   ```

## Project Notes and Planning Guidelines

### Scratchpad Usage
- Always create and maintain a `.scratchpad/` folder in each project root for temporary markdown files, task status, and planning documents
- Add `.scratchpad/` to the project's `.gitignore` file to keep notes local
- Use this folder to store:
  - Technical analysis and findings (`analysis-YYYY-MM-DD.md`)
  - Implementation plans and strategies (`plan-feature-name.md`)
  - Code refactoring ideas (`refactor-component-name.md`)
  - Architecture decisions and considerations (`architecture-decisions.md`)
  - Development progress and next steps (`progress-notes.md`)
  - Task status and temporary working documents

### Plan Documentation Process
1. **Default Behavior**: When asked to create plans, create individual markdown files in `.scratchpad/` folder
2. **File Naming**: Use descriptive names with dates when relevant:
   - `plan-agent-refactoring-2024-07-31.md`
   - `analysis-memory-system.md`
   - `task-status-current.md`
3. **Organization**: Each file should have clear headings, timestamps, and be self-contained

### Scratchpad Folder Structure Example
```
project_root/
├── .scratchpad/
│   ├── plan-agent-refactoring-2024-07-31.md
│   ├── analysis-hardcoded-names.md
│   ├── task-status-current.md
│   ├── architecture-decisions.md
│   └── progress-notes.md
├── .gitignore  # Contains .scratchpad/
└── ... other project files
```

### Individual File Structure Example
```markdown
# Agent Name Refactoring Plan
*Created: 2024-07-31*

## Investigation Summary
- Found hardcoded constants in multiple files
- Plan to centralize in constants.py

## Implementation Strategy
- Phase 1: Extend constants
- Phase 2: Update core infrastructure
- [Detailed steps follow...]

## Next Steps
- [ ] Implement constants centralization
- [ ] Create utility methods
```

## Docker Build and Deployment

When building and pushing Docker containers, create a shell script following this pattern:

```bash
#!/bin/bash

# Exit on error
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
ECR_REPO_NAME="your_app_name"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME"

# Login to Amazon ECR
echo "Logging in to Amazon ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Create repository if it doesn't exist
echo "Creating ECR repository if it doesn't exist..."
aws ecr describe-repositories --repository-names "$ECR_REPO_NAME" --region "$AWS_REGION" || \
    aws ecr create-repository --repository-name "$ECR_REPO_NAME" --region "$AWS_REGION"

# Build the Docker image
echo "Building Docker image..."
docker build -f "$PARENT_DIR/Dockerfile" -t "$ECR_REPO_NAME" "$PARENT_DIR"

# Tag the image
echo "Tagging image..."
docker tag "$ECR_REPO_NAME":latest "$ECR_REPO_URI":latest

# Push the image to ECR
echo "Pushing image to ECR..."
docker push "$ECR_REPO_URI":latest

echo "Successfully built and pushed image to:"
echo "$ECR_REPO_URI:latest"

# Save the container URI to a file for reference
echo "$ECR_REPO_URI:latest" > "$SCRIPT_DIR/.container_uri"
```

### Docker Script Best Practices
- Always use `set -e` to exit on error
- Use environment variables for configuration with sensible defaults
- Login to ECR before pushing
- Create ECR repository if it doesn't exist
- Use clear echo statements to show progress (avoid emojis for compatibility)
- Save container URI to a file for reference by other scripts

### ARM64 Support
For ARM64 builds, add QEMU setup:
```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
DOCKER_BUILDKIT=0 docker build -f "$PARENT_DIR/Dockerfile" -t "$ECR_REPO_NAME" "$PARENT_DIR"
```

## GitHub Issue Management

### Label Management Best Practices
When creating GitHub issues:

1. **Check Available Labels First**: Always get a list of available labels for the repository before creating issues
   ```bash
   gh label list
   ```

2. **Use Only Existing Labels**: Only apply labels that already exist in the repository to avoid errors during issue creation

3. **Suggest New Labels**: If you believe a new label would be beneficial, make a suggestion in the issue description or as a separate comment, but don't attempt to add non-existent labels during issue creation

4. **Label Application**: Apply labels that are available and relevant to the issue type and scope

**Example Workflow**:
```bash
# First check available labels
gh label list

# Create issue with only existing labels
gh issue create --title "..." --body-file "..." --label "enhancement,bug"

# If new labels are needed, suggest them in issue comments
gh issue comment 123 --body "Suggest adding 'agentcore' label for AgentCore-related issues"
```

## Summary
These guidelines ensure consistent, maintainable, and modern Python code. Always prioritize simplicity and clarity over cleverness.
## Federated Registry Implementation Workflow

When implementing the federated registry feature, follow this 3-agent workflow for each sub-feature:

### Agent Roles
1. **Writer Agent** - Implement code following CLAUDE.md standards
2. **Reviewer Agent** - Analyze time/space complexity, evaluate trade-offs, check production readiness
3. **Tester Agent** - Write property-based tests, integration tests, validate acceptance criteria

### Workflow Per Sub-Feature
1. Writer Agent implements all tasks
2. Reviewer Agent analyzes and suggests improvements
3. Writer Agent addresses reviewer suggestions
4. Tester Agent writes tests and validates
5. Update plan if new scope discovered
6. Final validation before marking complete

### Quality Gates
- All acceptance criteria verified with tests
- Reviewer approved production readiness
- Property-based tests cover invariants
- No TODO or FIXME left unaddressed
- Code compiles without warnings
- Existing tests still pass
