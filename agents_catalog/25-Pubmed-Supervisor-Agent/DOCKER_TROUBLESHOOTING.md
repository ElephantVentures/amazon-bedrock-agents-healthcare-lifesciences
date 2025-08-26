# Docker Deployment Troubleshooting Guide

## Architecture Issues

### Problem: `qemu-x86_64: Could not open '/lib64/ld-linux-x86-64.so.2'`

This error occurs when there's a platform architecture mismatch, typically on Apple Silicon (ARM64) Macs trying to run x86_64 containers.

### Solutions

#### Option 1: Automatic Architecture Detection (Recommended)
The deployment script now automatically detects your architecture and uses the appropriate Docker configuration.

```bash
# Clean any existing builds
./docker-deploy.sh clean

# Rebuild with correct architecture
./docker-deploy.sh build

# Deploy
./docker-deploy.sh deploy
```

#### Option 2: Manual Architecture Selection

**For Apple Silicon (ARM64) Macs:**
```bash
# Use ARM64-optimized configuration
docker-compose -f docker-compose.arm64.yml build
docker-compose -f docker-compose.arm64.yml --env-file .env run --rm pubmed-deployment
```

**For x86_64 systems:**
```bash
# Use x86_64 configuration
docker-compose -f docker-compose.yml build
docker-compose -f docker-compose.yml --env-file .env run --rm pubmed-deployment
```

#### Option 3: Enable Rosetta Emulation (Apple Silicon only)

1. Open Docker Desktop
2. Go to Settings → General
3. Enable "Use Rosetta for x86/amd64 emulation on Apple Silicon"
4. Restart Docker Desktop
5. Rebuild the image:

```bash
./docker-deploy.sh clean
./docker-deploy.sh build
```

## Common Docker Issues

### Issue: Docker Compose Not Found
```bash
# Check if Docker Compose is available
docker compose version
# or
docker-compose version
```

**Solution:**
- Install Docker Desktop (includes Compose)
- Or install Docker Compose separately

### Issue: Permission Denied
```bash
# Make sure scripts are executable
chmod +x docker-deploy.sh deploy.sh
```

### Issue: Build Cache Problems
```bash
# Clear Docker build cache
docker system prune -a -f

# Rebuild from scratch
./docker-deploy.sh clean
./docker-deploy.sh build
```

### Issue: AWS Credentials Not Found
```bash
# Validate your environment file
cat .env

# Check AWS credentials are set
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY

# Test AWS connectivity
./docker-deploy.sh validate
```

## Architecture-Specific Notes

### Apple Silicon (ARM64) Considerations
- **Performance**: ARM64 builds run natively and are faster
- **Compatibility**: AWS Lambda runs on x86_64, but our deployment tools work fine on ARM64
- **Python packages**: All required packages have ARM64 support

### x86_64 Considerations
- **Standard**: Most cloud environments use x86_64
- **Compatibility**: Direct compatibility with AWS Lambda runtime
- **Performance**: Native performance on x86_64 systems

## Debug Mode

For detailed troubleshooting, use the interactive shell:

```bash
./docker-deploy.sh shell

# Inside the container, you can:
aws --version
python --version
pip list
aws sts get-caller-identity
```

## Environment Variables Debug

```bash
# Check all environment variables in container
./docker-deploy.sh shell
env | grep -E "(AWS|BUCKET|REGION)"
```

## Logs and Monitoring

```bash
# View container logs
docker logs pubmed-agent-deployment

# Monitor deployment in real-time
docker-compose -f docker-compose.yml --env-file .env run pubmed-deployment
```

## Reset Everything

If you encounter persistent issues:

```bash
# Complete reset
./docker-deploy.sh clean
docker system prune -a -f
rm -f .env

# Start fresh
cp env.example .env
# Edit .env with your values
./docker-deploy.sh validate
./docker-deploy.sh deploy
```

## Getting Help

1. **Check Logs**: Always check the full deployment logs for specific error messages
2. **Validate Environment**: Use `./docker-deploy.sh validate` before deploying
3. **Architecture**: Ensure you're using the right Docker configuration for your system
4. **AWS Permissions**: Verify your AWS credentials have the necessary permissions
5. **Docker Version**: Ensure you're using a recent version of Docker Desktop

## Supported Platforms

- ✅ macOS (Intel x86_64)
- ✅ macOS (Apple Silicon ARM64)
- ✅ Linux x86_64
- ✅ Linux ARM64
- ✅ Windows with WSL2

## Quick Architecture Check

```bash
# Check your system architecture
uname -m

# Check Docker platform
docker version --format '{{.Server.Arch}}'

# Check what images you have
docker images | grep pubmed
```
