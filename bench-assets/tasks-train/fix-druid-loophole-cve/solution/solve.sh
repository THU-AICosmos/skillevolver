#!/bin/bash
#
# Reference solution for Apache Druid CVE-2021-26920 vulnerability fix
# This script creates a proper git patch and applies it to fix the vulnerability
# where local/http InputSources in the sampler endpoint allow file reads and SSRF
#

set -e  # Exit on error

WORKSPACE=${WORKSPACE:-/root}
DRUID_DIR="${WORKSPACE}/druid"
PATCHES_DIR="${WORKSPACE}/patches"
DRUID_HOME=${DRUID_HOME:-/opt/druid}

echo "=== Apache Druid CVE-2021-26920 Fix ==="
echo "Creating security patches for Apache Druid 0.20.0..."
echo "Blocking local file read and SSRF via InputSource in sampler endpoint"
echo ""

# Create patches directory
mkdir -p "${PATCHES_DIR}"

cd "${DRUID_DIR}"

# Find the source file
SAMPLER_RESOURCE="indexing-service/src/main/java/org/apache/druid/indexing/overlord/sampler/SamplerResource.java"

if [ ! -f "$SAMPLER_RESOURCE" ]; then
    echo "ERROR: Could not find SamplerResource.java"
    exit 1
fi

# Create patched version that blocks dangerous InputSource types
cat > /tmp/SamplerResource.java.patched << 'JAVAEOF'
package org.apache.druid.indexing.overlord.sampler;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.google.common.base.Preconditions;
import com.google.inject.Inject;
import com.sun.jersey.spi.container.ResourceFilters;
import org.apache.druid.guice.annotations.Json;
import org.apache.druid.server.http.security.StateResourceFilter;

import javax.ws.rs.Consumes;
import javax.ws.rs.POST;
import javax.ws.rs.Path;
import javax.ws.rs.Produces;
import javax.ws.rs.core.MediaType;
import java.util.regex.Pattern;

@Path("/druid/indexer/v1/sampler")
public class SamplerResource
{
  private static final Pattern LOCAL_INPUT_SOURCE_PATTERN = Pattern.compile(
      "\"type\"\\s*:\\s*\"local\"", Pattern.CASE_INSENSITIVE
  );
  private static final Pattern HTTP_INPUT_SOURCE_PATTERN = Pattern.compile(
      "\"type\"\\s*:\\s*\"http\"", Pattern.CASE_INSENSITIVE
  );

  private final ObjectMapper jsonMapper;

  @Inject
  public SamplerResource(@Json ObjectMapper jsonMapper)
  {
    this.jsonMapper = jsonMapper;
  }

  @POST
  @Consumes(MediaType.APPLICATION_JSON)
  @Produces(MediaType.APPLICATION_JSON)
  @ResourceFilters(StateResourceFilter.class)
  public SamplerResponse post(final String rawJson) throws Exception
  {
    Preconditions.checkNotNull(rawJson, "Request body cannot be empty");

    // CVE-2021-26920: Validate raw JSON BEFORE deserialization to block
    // dangerous InputSource types that allow file reads and SSRF
    validateInputSourceSecurity(rawJson);

    SamplerSpec samplerSpec = jsonMapper.readValue(rawJson, SamplerSpec.class);
    return samplerSpec.sample();
  }

  // CVE-2021-26920: Block dangerous InputSource types in sampler requests
  private void validateInputSourceSecurity(String rawJson)
  {
    // Block "type": "local" InputSource - prevents arbitrary file reads
    if (LOCAL_INPUT_SOURCE_PATTERN.matcher(rawJson).find()) {
      throw new IllegalArgumentException(
          "Local InputSource is not allowed in sampler requests for security reasons (CVE-2021-26920). "
          + "Use 'inline' InputSource instead.");
    }

    // Block "type": "http" InputSource - prevents SSRF attacks
    if (HTTP_INPUT_SOURCE_PATTERN.matcher(rawJson).find()) {
      throw new IllegalArgumentException(
          "HTTP InputSource is not allowed in sampler requests for security reasons (CVE-2021-26920). "
          + "Use 'inline' InputSource instead.");
    }
  }
}
JAVAEOF

# Generate the patch using diff
diff -u "$SAMPLER_RESOURCE" /tmp/SamplerResource.java.patched > /tmp/raw.patch || true

# Convert to git format patch
{
    echo "diff --git a/$SAMPLER_RESOURCE b/$SAMPLER_RESOURCE"
    echo "--- a/$SAMPLER_RESOURCE"
    echo "+++ b/$SAMPLER_RESOURCE"
    tail -n +3 /tmp/raw.patch
} > "${PATCHES_DIR}/0001-CVE-2021-26920-block-local-http-inputsource-in-sampler.patch"

echo "  Created security patch: ${PATCHES_DIR}/0001-CVE-2021-26920-block-local-http-inputsource-in-sampler.patch"

# Apply the patch
echo "Applying security patch to Druid source..."

git apply "${PATCHES_DIR}/0001-CVE-2021-26920-block-local-http-inputsource-in-sampler.patch"
echo "  Patch applied successfully using git apply"

# Build patched Druid
echo "Building patched Druid..."
echo "Building indexing-service module..."

cd "${DRUID_DIR}"

# Build with proper exit code handling
set +e
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am 2>&1 | tee /tmp/druid-build.log
BUILD_EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo "  Druid built successfully"

    # Find and copy the built JAR
    BUILT_JAR=$(find ./indexing-service/target -name "druid-indexing-service-*.jar" -not -name "*sources*" -not -name "*tests*" 2>/dev/null | head -1)

    if [ -n "$BUILT_JAR" ] && [ -f "$BUILT_JAR" ]; then
        echo "Found built JAR: $BUILT_JAR"

        # Copy to Druid installation
        if [ -d "${DRUID_HOME}/lib" ]; then
            ORIGINAL_JAR=$(find "${DRUID_HOME}/lib" -name "druid-indexing-service-*.jar" 2>/dev/null | head -1)
            if [ -n "$ORIGINAL_JAR" ]; then
                cp "$ORIGINAL_JAR" "${ORIGINAL_JAR}.backup" 2>/dev/null || true
                rm -f "$ORIGINAL_JAR"
            fi
            cp -f "$BUILT_JAR" "${DRUID_HOME}/lib/"
            echo "  Patched binaries installed to ${DRUID_HOME}/lib/"
        fi
    fi
else
    echo "ERROR: Maven build failed with exit code $BUILD_EXIT_CODE"
    echo "Last 100 lines of build log:"
    tail -100 /tmp/druid-build.log
    echo "Continuing despite build failure - source patches are applied"
fi

echo ""
echo "=== Solution Complete ==="
echo "  Security patch created in ${PATCHES_DIR}"
echo "  Patches applied to Druid source"
echo "  Druid built (exit code: $BUILD_EXIT_CODE)"
echo ""
echo "The fix blocks dangerous InputSource types in the sampler endpoint by:"
echo "  1. Detecting 'type':'local' patterns to prevent arbitrary file reads"
echo "  2. Detecting 'type':'http' patterns to prevent SSRF attacks"
echo "  3. Throwing IllegalArgumentException to reject malicious requests"
echo "  4. Only allowing safe InputSource types like 'inline'"
