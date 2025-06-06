#!/bin/bash

set -e

if [ "$IS_PULL_REQUEST" -eq 1 ]; then
    echo "Checking if bucket $PROJECT_NAME-$BRANCH_NAME exists..."

    if aws s3api head-bucket --bucket "$PROJECT_NAME-$BRANCH_NAME" 2>/dev/null; then
        echo "Bucket $PROJECT_NAME-$BRANCH_NAME already exists."
    else
        echo "Bucket $PROJECT_NAME-$BRANCH_NAME does not exist. Creating bucket..."
        
        if ! aws s3api create-bucket --bucket "$PROJECT_NAME-$BRANCH_NAME" --region "$AWS_DEFAULT_REGION" --create-bucket-configuration LocationConstraint="$AWS_DEFAULT_REGION"; then
            echo "Error: Failed to create bucket."
            exit 1
        fi
        if ! aws s3api put-public-access-block --bucket "$PROJECT_NAME-$BRANCH_NAME" --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" --region "$AWS_DEFAULT_REGION"; then
            echo "Error: Failed to configure public access block."
            exit 1
        fi
        if ! aws s3api put-bucket-ownership-controls --bucket "$PROJECT_NAME-$BRANCH_NAME" --ownership-controls="Rules=[{ObjectOwnership=BucketOwnerPreferred}]" --region "$AWS_DEFAULT_REGION"; then
            echo "Error: Failed to configure bucket ownership controls."
            exit 1
        fi
        if ! aws s3api put-bucket-acl --bucket "$PROJECT_NAME-$BRANCH_NAME" --acl public-read --region "$AWS_DEFAULT_REGION"; then
            echo "Error: Failed to configure bucket ACL."
            exit 1
        fi
        if ! aws s3api put-bucket-website --bucket "$PROJECT_NAME-$BRANCH_NAME" --crm-configuration file://crm_configuration.json --region "$AWS_DEFAULT_REGION"; then
            echo "Error: Failed to configure static crm hosting."
            exit 1
        fi
        if ! aws s3api put-bucket-policy --bucket "$PROJECT_NAME-$BRANCH_NAME" --policy file://s3_policy.json --region "$AWS_DEFAULT_REGION"; then
            echo "Error: Failed to configure bucket policy."
            exit 1
        fi
    fi
fi
