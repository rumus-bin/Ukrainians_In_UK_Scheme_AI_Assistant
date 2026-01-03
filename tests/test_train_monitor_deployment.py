"""
Deployment verification tests for Train Monitor Docker integration.

Verifies that Docker Compose configuration is valid and
train-monitor service is properly defined.
"""

import sys
from pathlib import Path
import subprocess
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logger, get_logger

# Setup logging
setup_logger()
logger = get_logger()


def test_docker_compose_syntax():
    """Test that docker-compose.yml has valid syntax."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Docker Compose Syntax Validation")
    logger.info("=" * 70)

    docker_compose_path = project_root / "docker-compose.yml"

    assert docker_compose_path.exists(), "docker-compose.yml not found"

    # Validate syntax using docker compose config
    try:
        result = subprocess.run(
            ["docker", "compose", "config", "--quiet"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10
        )

        # Exit code 0 means valid
        assert result.returncode == 0, f"Invalid docker-compose.yml: {result.stderr}"

        logger.info("✅ docker-compose.yml syntax is valid")

    except subprocess.TimeoutExpired:
        raise AssertionError("docker compose config command timed out")
    except FileNotFoundError:
        raise AssertionError("docker or docker-compose not installed")


def test_train_monitor_service_defined():
    """Test that train-monitor service is defined in docker-compose.yml."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Train Monitor Service Definition")
    logger.info("=" * 70)

    docker_compose_path = project_root / "docker-compose.yml"

    # Load docker-compose.yml
    with open(docker_compose_path, 'r') as f:
        compose_config = yaml.safe_load(f)

    # Check services section exists
    assert "services" in compose_config, "No services section in docker-compose.yml"

    # Check train-monitor service exists
    services = compose_config["services"]
    assert "train-monitor" in services, "train-monitor service not defined"

    logger.info("✅ train-monitor service is defined")

    # Verify key fields
    train_monitor = services["train-monitor"]

    assert "container_name" in train_monitor, "container_name not set"
    assert train_monitor["container_name"] == "ukraine-bot-train-monitor", \
        "Wrong container name"

    assert "command" in train_monitor, "command not set"
    assert "src.train_monitor.monitor" in train_monitor["command"], \
        "Wrong command for train-monitor"

    assert "healthcheck" in train_monitor, "healthcheck not defined"
    assert "restart" in train_monitor, "restart policy not set"

    logger.info(f"✅ Container name: {train_monitor['container_name']}")
    logger.info(f"✅ Command: {train_monitor['command']}")
    logger.info(f"✅ Restart policy: {train_monitor['restart']}")
    logger.info(f"✅ Health check: configured")


def test_env_example_has_train_monitor():
    """Test that .env.example contains train monitor configuration."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Environment Variables Documentation")
    logger.info("=" * 70)

    env_example_path = project_root / ".env.example"

    assert env_example_path.exists(), ".env.example not found"

    # Read .env.example
    with open(env_example_path, 'r') as f:
        env_content = f.read()

    # Check for required sections
    required_vars = [
        "TRAIN_MONITOR_ENABLED",
        "TRAIN_MONITOR_DRY_RUN",
        "TRAIN_MONITOR_PROVIDER_TYPE",
        "DARWIN_API_KEY",
        "TRAIN_MONITOR_STATIONS",
        "TRAIN_MONITOR_ELY_ENABLED",
        "TRAIN_MONITOR_CBG_ENABLED",
    ]

    for var in required_vars:
        assert var in env_content, f"Missing {var} in .env.example"
        logger.info(f"✅ {var} documented")

    logger.info("✅ All required environment variables documented")


def test_train_monitor_volumes():
    """Test that train-monitor service has correct volume mounts."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Volume Mounts Configuration")
    logger.info("=" * 70)

    docker_compose_path = project_root / "docker-compose.yml"

    with open(docker_compose_path, 'r') as f:
        compose_config = yaml.safe_load(f)

    train_monitor = compose_config["services"]["train-monitor"]

    assert "volumes" in train_monitor, "No volumes defined"

    volumes = train_monitor["volumes"]

    # Check for required volumes
    required_volumes = [
        "./src:/app/src",
        "./logs:/app/logs",
        "./.env:/app/.env",
    ]

    for vol in required_volumes:
        assert vol in volumes, f"Missing volume: {vol}"
        logger.info(f"✅ Volume mounted: {vol}")

    logger.info("✅ All required volumes mounted")


def test_health_check_configuration():
    """Test that health check is properly configured."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST: Health Check Configuration")
    logger.info("=" * 70)

    docker_compose_path = project_root / "docker-compose.yml"

    with open(docker_compose_path, 'r') as f:
        compose_config = yaml.safe_load(f)

    train_monitor = compose_config["services"]["train-monitor"]
    healthcheck = train_monitor["healthcheck"]

    # Verify health check settings
    assert "test" in healthcheck, "Health check test not defined"
    assert "interval" in healthcheck, "Health check interval not defined"
    assert "timeout" in healthcheck, "Health check timeout not defined"
    assert "retries" in healthcheck, "Health check retries not defined"
    assert "start_period" in healthcheck, "Health check start_period not defined"

    logger.info(f"✅ Test command: {healthcheck['test']}")
    logger.info(f"✅ Interval: {healthcheck['interval']}")
    logger.info(f"✅ Timeout: {healthcheck['timeout']}")
    logger.info(f"✅ Retries: {healthcheck['retries']}")
    logger.info(f"✅ Start period: {healthcheck['start_period']}")

    # Verify health check looks for correct process
    test_cmd = " ".join(healthcheck["test"])
    assert "src.train_monitor.monitor" in test_cmd, \
        "Health check doesn't look for correct process"

    logger.info("✅ Health check properly configured")


def run_all_tests():
    """Run all deployment verification tests."""
    logger.info("\n" + "=" * 70)
    logger.info("TRAIN MONITOR DEPLOYMENT VERIFICATION TEST SUITE")
    logger.info("=" * 70)

    tests = [
        ("Docker Compose Syntax", test_docker_compose_syntax),
        ("Service Definition", test_train_monitor_service_defined),
        ("Environment Variables", test_env_example_has_train_monitor),
        ("Volume Mounts", test_train_monitor_volumes),
        ("Health Check", test_health_check_configuration),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            logger.error(f"\n❌ {test_name} FAILED: {e}")
        except Exception as e:
            failed += 1
            logger.exception(f"\n❌ {test_name} ERROR: {e}")

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total tests: {len(tests)}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"❌ Failed: {failed}")

    if failed == 0:
        logger.info("\n🎉 ALL DEPLOYMENT TESTS PASSED! 🎉")
        logger.info("=" * 70)
        logger.info("Docker integration is ready for deployment")
        logger.info("=" * 70)
    else:
        logger.error(f"\n⚠️ {failed} test(s) failed")

    logger.info("=" * 70)

    return failed == 0


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
        sys.exit(1)
