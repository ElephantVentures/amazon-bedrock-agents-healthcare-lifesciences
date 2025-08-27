#!/usr/bin/env python3

"""
Simple OpenAPI schema validator for Amazon Bedrock compatibility
"""

import json
import sys
from pathlib import Path

def validate_openapi_schema(schema_file):
    """Validate OpenAPI schema for Amazon Bedrock compatibility"""
    
    print(f"Validating {schema_file}...")
    
    try:
        with open(schema_file, 'r') as f:
            schema = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load JSON: {e}")
        return False
    
    errors = []
    warnings = []
    
    # Check required top-level fields
    required_fields = ['openapi', 'info', 'paths']
    for field in required_fields:
        if field not in schema:
            errors.append(f"Missing required field: {field}")
    
    # Check OpenAPI version
    if 'openapi' in schema:
        version = schema['openapi']
        if not version.startswith('3.0'):
            warnings.append(f"OpenAPI version {version} may not be fully supported. Recommend 3.0.0")
    
    # Check info section
    if 'info' in schema:
        info = schema['info']
        if 'title' not in info:
            errors.append("Missing info.title")
        if 'version' not in info:
            errors.append("Missing info.version")
    
    # Check paths
    if 'paths' in schema:
        paths = schema['paths']
        if not paths:
            errors.append("No paths defined")
        
        for path, path_obj in paths.items():
            if not isinstance(path_obj, dict):
                errors.append(f"Path {path} is not an object")
                continue
                
            for method, method_obj in path_obj.items():
                if not isinstance(method_obj, dict):
                    errors.append(f"Method {method} in path {path} is not an object")
                    continue
                
                # Check operationId
                if 'operationId' not in method_obj:
                    errors.append(f"Missing operationId for {method} {path}")
                
                # Check responses
                if 'responses' not in method_obj:
                    errors.append(f"Missing responses for {method} {path}")
                else:
                    responses = method_obj['responses']
                    if '200' not in responses:
                        warnings.append(f"No 200 response defined for {method} {path}")
                
                # Check for unsupported features
                unsupported_keywords = ['oneOf', 'anyOf', 'allOf']
                schema_str = json.dumps(method_obj)
                for keyword in unsupported_keywords:
                    if keyword in schema_str:
                        warnings.append(f"Found potentially unsupported keyword '{keyword}' in {method} {path}")
    
    # Report results
    if errors:
        print("❌ Validation failed with errors:")
        for error in errors:
            print(f"  • {error}")
    
    if warnings:
        print("⚠️  Warnings:")
        for warning in warnings:
            print(f"  • {warning}")
    
    if not errors and not warnings:
        print("✅ Schema validation passed")
    elif not errors:
        print("✅ Schema validation passed with warnings")
    
    return len(errors) == 0

def main():
    """Main validation function"""
    
    script_dir = Path(__file__).parent
    schema_dir = script_dir / "action_groups" / "pubmed_researcher"
    
    schemas = [
        schema_dir / "search_pubmed_schema.json",
        schema_dir / "read_pubmed_schema.json"
    ]
    
    print("🔍 Validating OpenAPI schemas for Amazon Bedrock compatibility")
    print("=" * 60)
    
    all_valid = True
    
    for schema_file in schemas:
        if not schema_file.exists():
            print(f"❌ Schema file not found: {schema_file}")
            all_valid = False
            continue
            
        is_valid = validate_openapi_schema(schema_file)
        all_valid = all_valid and is_valid
        print()
    
    if all_valid:
        print("🎉 All schemas are valid for Amazon Bedrock deployment!")
        return 0
    else:
        print("💥 Some schemas have issues that need to be fixed before deployment")
        return 1

if __name__ == "__main__":
    sys.exit(main())
