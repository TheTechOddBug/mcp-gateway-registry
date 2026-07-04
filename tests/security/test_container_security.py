"""
Unit tests for Docker container security configuration.

Tests verify that Dockerfiles follow CIS Docker Benchmark 4.1 requirements:
- Non-root USER directive
- No sudo package
- HEALTHCHECK directives
- Proper environment variables (PIP_NO_CACHE_DIR)
"""

import re
from pathlib import Path

import pytest

# List of Dockerfiles to test
DOCKERFILES = [
    "Dockerfile",
    "docker/Dockerfile.auth",
    "docker/Dockerfile.registry",
    "docker/Dockerfile.mcp-server",
    "docker/Dockerfile.mcp-server-light",
    "docker/Dockerfile.metrics-db",
    "docker/keycloak/Dockerfile",
    "metrics-service/Dockerfile",
    "terraform/aws-ecs/grafana/Dockerfile",
]


@pytest.fixture(scope="module")
def repo_root() -> Path:
    """Get repository root directory."""
    return Path(__file__).parent.parent.parent


def _extract_hcl_resource_block(content: str, resource_name: str) -> str:
    """Return the text of a named Terraform resource block via brace matching.

    Args:
        content: Full HCL file contents.
        resource_name: The resource label (second quoted token) to extract.

    Returns:
        The block text (from the opening brace to its matching close), or an
        empty string if the resource is not found.
    """
    marker = re.search(rf'resource\s+"[^"]+"\s+"{re.escape(resource_name)}"\s*{{', content)
    if not marker:
        return ""

    start = marker.end() - 1  # position of the opening brace
    depth = 0
    for idx in range(start, len(content)):
        char = content[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start : idx + 1]
    return ""


@pytest.mark.parametrize("dockerfile_path", DOCKERFILES)
def test_dockerfile_has_user_directive(repo_root: Path, dockerfile_path: str):
    """Test that Dockerfile has USER directive (CIS Docker Benchmark 4.1)."""
    dockerfile = repo_root / dockerfile_path
    assert dockerfile.exists(), f"Dockerfile not found: {dockerfile}"

    content = dockerfile.read_text()

    # Check for USER directive
    user_pattern = re.compile(r"^USER\s+\w+", re.MULTILINE)
    assert user_pattern.search(content), f"{dockerfile_path}: Missing USER directive (CIS 4.1)"


@pytest.mark.parametrize("dockerfile_path", DOCKERFILES)
def test_dockerfile_user_not_root(repo_root: Path, dockerfile_path: str):
    """Test that Dockerfile does not run as root user."""
    dockerfile = repo_root / dockerfile_path
    assert dockerfile.exists(), f"Dockerfile not found: {dockerfile}"

    content = dockerfile.read_text()

    # Find all USER directives
    user_lines = re.findall(r"^USER\s+(\w+)", content, re.MULTILINE)
    assert user_lines, f"{dockerfile_path}: No USER directive found"

    # Last USER directive should not be root
    last_user = user_lines[-1]
    assert last_user.lower() != "root", f"{dockerfile_path}: Last USER directive is 'root'"


@pytest.mark.parametrize("dockerfile_path", DOCKERFILES)
def test_dockerfile_no_sudo(repo_root: Path, dockerfile_path: str):
    """Test that Dockerfile does not install sudo package."""
    dockerfile = repo_root / dockerfile_path
    assert dockerfile.exists(), f"Dockerfile not found: {dockerfile}"

    content = dockerfile.read_text()

    # Check that sudo is not being installed
    assert "sudo" not in content, f"{dockerfile_path}: Contains 'sudo' package (security risk)"


@pytest.mark.parametrize("dockerfile_path", DOCKERFILES)
def test_dockerfile_has_healthcheck(repo_root: Path, dockerfile_path: str):
    """Test that Dockerfile has HEALTHCHECK directive."""
    dockerfile = repo_root / dockerfile_path
    assert dockerfile.exists(), f"Dockerfile not found: {dockerfile}"

    content = dockerfile.read_text()

    # Check for HEALTHCHECK directive
    healthcheck_pattern = re.compile(r"^HEALTHCHECK\s+", re.MULTILINE)
    assert healthcheck_pattern.search(content), f"{dockerfile_path}: Missing HEALTHCHECK directive"


@pytest.mark.parametrize(
    "dockerfile_path",
    [
        f
        for f in DOCKERFILES
        if not f.startswith("terraform/")  # Exclude Grafana (Node.js)
        and not f.endswith("metrics-db")  # Exclude alpine-based
    ],
)
def test_python_dockerfile_has_pip_no_cache(repo_root: Path, dockerfile_path: str):
    """Test that Python Dockerfiles set PIP_NO_CACHE_DIR=1."""
    dockerfile = repo_root / dockerfile_path
    assert dockerfile.exists(), f"Dockerfile not found: {dockerfile}"

    content = dockerfile.read_text()

    # Check if it's a Python-based image
    if re.search(r"FROM.*python", content, re.IGNORECASE):
        # Check for PIP_NO_CACHE_DIR
        assert (
            "PIP_NO_CACHE_DIR" in content
        ), f"{dockerfile_path}: Python image missing PIP_NO_CACHE_DIR"


def test_docker_compose_has_security_options(repo_root: Path):
    """Test that docker-compose.yml has security hardening options."""
    compose_file = repo_root / "docker-compose.yml"
    assert compose_file.exists(), "docker-compose.yml not found"

    content = compose_file.read_text()

    # Check for security_opt
    assert "security_opt:" in content, "docker-compose.yml missing security_opt"
    assert "no-new-privileges:true" in content, "docker-compose.yml missing no-new-privileges"

    # Check for cap_drop
    assert "cap_drop:" in content, "docker-compose.yml missing cap_drop"
    assert "- ALL" in content, "docker-compose.yml missing cap_drop: ALL"


def test_docker_compose_mongodb_cap_add(repo_root: Path):
    """Test that all docker-compose files restore SETUID/SETGID for MongoDB after cap_drop ALL.

    MongoDB uses gosu to switch from root to the mongodb user at startup.
    gosu requires SETUID and SETGID capabilities. Without them, MongoDB
    fails with: 'error: failed switching to mongodb: operation not permitted'.

    Regression introduced in PR #624 and PR #651 where cap_drop: ALL was applied
    to all services without adding back the minimum capabilities required by MongoDB.
    Fixed in PR #688.
    """
    compose_files = [
        "docker-compose.yml",
        "docker-compose.prebuilt.yml",
        "docker-compose.podman.yml",
    ]
    for compose_filename in compose_files:
        compose_file = repo_root / compose_filename
        assert compose_file.exists(), f"{compose_filename} not found"

        content = compose_file.read_text()

        assert "cap_add:" in content, f"{compose_filename}: missing cap_add for MongoDB"
        assert (
            "- SETUID" in content
        ), f"{compose_filename}: missing SETUID in cap_add (required by MongoDB gosu)"
        assert (
            "- SETGID" in content
        ), f"{compose_filename}: missing SETGID in cap_add (required by MongoDB gosu)"


def test_docker_compose_registry_port_mapping(repo_root: Path):
    """Test that docker-compose.yml maps nginx to high ports."""
    compose_file = repo_root / "docker-compose.yml"
    assert compose_file.exists(), "docker-compose.yml not found"

    content = compose_file.read_text()

    # Check for port mapping 80:8080 and 443:8443
    assert '"80:8080"' in content or "'80:8080'" in content, "Missing port mapping 80:8080"
    assert '"443:8443"' in content or "'443:8443'" in content, "Missing port mapping 443:8443"


# IAM policy files that grant AgentCore federation access. Both the Terraform and
# CDK stacks must express the same least-privilege posture.
AGENTCORE_IAM_FILES = [
    "terraform/aws-ecs/modules/mcp-gateway/iam.tf",
    "infra/lib/registry/registry-service-stack.ts",
]


class TestBedrockAgentCoreLeastPrivilege:
    """Guard the AgentCore federation IAM grant against wildcard privilege creep.

    The registry federation client is read-only against the
    bedrock-agentcore-control plane. The IAM policy must therefore never grant
    the full `bedrock-agentcore:*` action or a `Resource = "*"` on those actions,
    and must never allow `sts:AssumeRole` on an unconstrained resource.
    """

    @pytest.mark.parametrize("iam_path", AGENTCORE_IAM_FILES)
    def test_no_full_agentcore_wildcard_action(self, repo_root: Path, iam_path: str):
        """The policy must not grant the full bedrock-agentcore:* action.

        Matches the wildcard only when it is an *action* (the `*` terminates the
        service:action string, i.e. is quote-delimited), not the region field of
        a scoped resource ARN like `...:bedrock-agentcore:*:<account>:*`.
        """
        iam_file = repo_root / iam_path
        assert iam_file.exists(), f"IAM file not found: {iam_file}"

        content = iam_file.read_text()
        wildcard_action = re.compile(r"""bedrock-agentcore:\*["']""")
        assert not wildcard_action.search(content), (
            f"{iam_path}: grants full 'bedrock-agentcore:*' action -- scope to the "
            f"specific read operations the federation client uses."
        )

    @pytest.mark.parametrize("iam_path", AGENTCORE_IAM_FILES)
    def test_only_read_agentcore_actions(self, repo_root: Path, iam_path: str):
        """Only the read operations the client actually calls may be granted."""
        iam_file = repo_root / iam_path
        content = iam_file.read_text()

        granted = set(re.findall(r"bedrock-agentcore:([A-Za-z]+)", content))
        allowed = {"ListRegistries", "ListRegistryRecords", "GetRegistryRecord"}
        unexpected = granted - allowed
        assert not unexpected, (
            f"{iam_path}: grants unexpected AgentCore actions {sorted(unexpected)}; "
            f"the federation client is read-only (allowed: {sorted(allowed)})."
        )
        assert granted, f"{iam_path}: no bedrock-agentcore action found -- policy may have moved."

    def test_terraform_agentcore_resource_scoped(self, repo_root: Path):
        """Terraform AgentCore read statement must scope Resource to the account.

        A `Resource = "*"` on the read actions is the reported over-broad grant.
        The scoped ARN pins the deploying account id. This asserts against the
        `bedrock_agentcore_access` policy block only (other policies such as ECS
        Exec legitimately use `Resource = "*"` for ssmmessages).
        """
        iam_file = repo_root / "terraform/aws-ecs/modules/mcp-gateway/iam.tf"
        block = _extract_hcl_resource_block(iam_file.read_text(), "bedrock_agentcore_access")
        assert block, "iam.tf: bedrock_agentcore_access policy resource not found."

        # The scoped resource ARN must be present.
        assert (
            "arn:${data.aws_partition.current.partition}:bedrock-agentcore:" in block
        ), "iam.tf: AgentCore read statement must scope Resource to an account-bound ARN."
        # The AgentCore policy must not fall back to a bare wildcard resource.
        assert (
            'Resource = "*"' not in block
        ), 'iam.tf: bedrock_agentcore_access must not use Resource = "*".'

    def test_terraform_sts_not_wildcard(self, repo_root: Path):
        """sts:AssumeRole must target configured role ARNs, never Resource = "*"."""
        iam_file = repo_root / "terraform/aws-ecs/modules/mcp-gateway/iam.tf"
        content = iam_file.read_text()

        # The assume-role resource must reference the configured ARN list.
        assert (
            "var.aws_registry_federation_assume_role_arns" in content
        ), "iam.tf: sts:AssumeRole must scope Resource to the configured role ARNs."

    def test_cdk_agentcore_resource_scoped(self, repo_root: Path):
        """CDK AgentCore statement must scope resources to the account, not '*'."""
        stack_file = repo_root / "infra/lib/registry/registry-service-stack.ts"
        content = stack_file.read_text()

        assert "arn:${this.partition}:bedrock-agentcore:" in content, (
            "registry-service-stack.ts: AgentCore statement must scope resources "
            "to an account-bound ARN."
        )
        assert (
            "resources: ['*']" not in content
        ), "registry-service-stack.ts: no statement may use resources: ['*']."
