"""
Test suite for Spring Boot 2 to 3 Migration Task verification (Product Catalog Variant).
Validates that the migration was completed correctly.
"""

import os
import re
import subprocess

WORKSPACE_DIR = "/workspace"


class TestJakartaNamespaceMigration:
    """Test that all javax.* imports have been migrated to jakarta.*"""

    def _collect_java_sources(self):
        """Collect all Java source files in the workspace"""
        sources = []
        src_dir = os.path.join(WORKSPACE_DIR, "src")
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith(".java"):
                    sources.append(os.path.join(root, f))
        return sources

    def test_no_javax_validation_imports(self):
        """Verify no javax.validation imports remain"""
        for src_file in self._collect_java_sources():
            with open(src_file) as fh:
                text = fh.read()
            assert "javax.validation" not in text, f"Found javax.validation in {src_file}"

    def test_product_uses_jakarta_persistence(self):
        """Verify jakarta.persistence is used in Product entity"""
        product_java = os.path.join(
            WORKSPACE_DIR,
            "src/main/java/com/example/catalogservice/model/Product.java",
        )
        assert os.path.exists(product_java), "Product.java not found"

        with open(product_java) as fh:
            text = fh.read()

        assert "jakarta.persistence" in text, "Product.java should use jakarta.persistence"

    def test_create_product_request_uses_jakarta_validation(self):
        """Verify jakarta.validation is used in CreateProductRequest DTO"""
        request_java = os.path.join(
            WORKSPACE_DIR,
            "src/main/java/com/example/catalogservice/dto/CreateProductRequest.java",
        )
        assert os.path.exists(request_java), "CreateProductRequest.java not found"

        with open(request_java) as fh:
            text = fh.read()

        assert "jakarta.validation" in text, "CreateProductRequest.java should use jakarta.validation"


class TestSecurityConfigMigration:
    """Test Spring Security 6 migration"""

    def test_uses_enable_method_security(self):
        """Verify @EnableMethodSecurity replaces @EnableGlobalMethodSecurity"""
        sec_config = os.path.join(
            WORKSPACE_DIR,
            "src/main/java/com/example/catalogservice/config/SecurityConfig.java",
        )
        with open(sec_config) as fh:
            text = fh.read()

        assert "EnableGlobalMethodSecurity" not in text, "Should not use deprecated @EnableGlobalMethodSecurity"
        assert "EnableMethodSecurity" in text, "Should use @EnableMethodSecurity"

    def test_uses_request_matchers(self):
        """Verify requestMatchers is used instead of antMatchers"""
        sec_config = os.path.join(
            WORKSPACE_DIR,
            "src/main/java/com/example/catalogservice/config/SecurityConfig.java",
        )
        with open(sec_config) as fh:
            text = fh.read()

        assert "antMatchers" not in text, "Should not use deprecated antMatchers"
        assert "requestMatchers" in text, "Should use requestMatchers"


class TestRestClientMigration:
    """Test RestTemplate to RestClient migration"""

    def test_external_pricing_uses_rest_client(self):
        """Verify RestClient is used in ExternalPricingService"""
        pricing_service = os.path.join(
            WORKSPACE_DIR,
            "src/main/java/com/example/catalogservice/service/ExternalPricingService.java",
        )
        with open(pricing_service) as fh:
            text = fh.read()

        assert "RestClient" in text, "Should use RestClient"


class TestProjectBuildAndTests:
    """Test that the project builds and tests pass"""

    def test_maven_compilation(self):
        """Verify the project compiles without errors"""
        result = subprocess.run(
            ["bash", "-c", "source /root/.sdkman/bin/sdkman-init.sh && sdk use java 21.0.2-tem && mvn clean compile -q"],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, f"Maven compile failed: {result.stdout}\n{result.stderr}"

    def test_maven_unit_tests(self):
        """Verify all unit tests pass"""
        result = subprocess.run(
            ["bash", "-c", "source /root/.sdkman/bin/sdkman-init.sh && sdk use java 21.0.2-tem && mvn test -q"],
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, f"Maven test failed: {result.stdout}\n{result.stderr}"


class TestPomDependencyUpdates:
    """Test that deprecated dependencies have been updated"""

    def test_no_javax_xml_bind(self):
        """Verify old JAXB API dependency is removed"""
        pom_file = os.path.join(WORKSPACE_DIR, "pom.xml")
        with open(pom_file) as fh:
            text = fh.read()

        assert "javax.xml.bind" not in text, "Old javax.xml.bind JAXB dependency should be removed"

    def test_no_legacy_jjwt_artifact(self):
        """Verify old single jjwt dependency is replaced with modular version"""
        pom_file = os.path.join(WORKSPACE_DIR, "pom.xml")
        with open(pom_file) as fh:
            text = fh.read()

        old_jjwt_match = re.search(
            r"<artifactId>jjwt</artifactId>\s*<version>0\.9",
            text,
            re.DOTALL,
        )
        assert old_jjwt_match is None, "Should not use old jjwt 0.9.x single artifact"
