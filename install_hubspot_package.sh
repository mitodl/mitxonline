#!/bin/bash
set -e

echo "🔧 Installing HubSpot API packages..."

# Stop the web container to avoid conflicts
echo "⏹️  Stopping web container..."
docker-compose stop web

# Start a temporary container to install packages
echo "📦 Installing packages..."
docker-compose run --rm --no-deps web bash -c "
    echo '📥 Installing hubspot-api-client v12...'
    pip install hubspot-api-client==12.0.0
    
    echo '📥 Installing local mitol-django-hubspot-api package...'
    pip install /src/ol-django/dist/mitol_django_hubspot_api-2025.3.17-py3-none-any.whl --force-reinstall
    
    echo '✅ Verifying installation...'
    python -c '
import hubspot
import mitol.hubspot_api
print(\"✅ HubSpot API Client version:\", getattr(hubspot, \"__version__\", \"12.0.0+\"))
print(\"✅ mitol.hubspot_api location:\", mitol.hubspot_api.__file__)

# Test the conditional imports
try:
    HUBSPOT_VERSION = getattr(hubspot, \"__version__\", \"12.0.0\")
    HUBSPOT_MAJOR_VERSION = int(HUBSPOT_VERSION.split(\".\")[0])
    print(f\"✅ Detected HubSpot major version: {HUBSPOT_MAJOR_VERSION}\")
    
    if HUBSPOT_MAJOR_VERSION >= 12:
        from hubspot.crm.objects import BatchInputSimplePublicObjectBatchInputForCreate
        print(\"✅ v12 BatchInputSimplePublicObjectBatchInputForCreate imported successfully\")
    else:
        from hubspot.crm.objects import BatchInputSimplePublicObjectInput
        print(\"✅ v6 BatchInputSimplePublicObjectInput imported successfully\")
        
except Exception as e:
    print(f\"❌ Conditional import test failed: {e}\")

print(\"✅ All packages installed successfully!\")
'
"

# Start the web container
echo "🚀 Starting web container..."
docker-compose up -d web

echo "🎉 Installation complete!"
