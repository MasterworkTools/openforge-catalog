# Deployment Setup

## NPM Commands

The following npm commands are available for deployment:

- `npm run deploy:staging` - Build and deploy to staging S3 bucket
- `npm run deploy:production` - Build and deploy to production S3 bucket

## GitHub Actions Setup

The GitHub Actions workflows will automatically deploy the frontend after a successful Docker build.

### Required GitHub Repository Variables

The following variables need to be set in the GitHub repository settings:

#### For Staging (test branch)
- `ECR_IAM_STAGING` - IAM role for both ECR and S3 access

#### For Production (main branch)
- `ECR_IAM_PROD` - IAM role for both ECR and S3 access

**Note**: The same IAM roles are used for both ECR and S3 access. These roles should have permissions for:
- ECR: Push images to the respective ECR repositories
- S3: Write access to the respective S3 buckets (staging-openforge-catalog-website and production-openforge-catalog-website)

### S3 Bucket Names

The deployment expects the following S3 buckets:
- Staging: `s3://staging-openforge-catalog-website/`
- Production: `s3://production-openforge-catalog-website/`

### Deployment Structure

Deployments are organized by git SHA:
- `s3://staging-openforge-catalog-website/{SHA}/`
- `s3://production-openforge-catalog-website/{SHA}/`

This allows for easy rollbacks and tracking of deployed versions.

### Local Deployment

For local deployment, ensure you have AWS CLI configured with appropriate credentials:

```bash
# Deploy to staging
npm run deploy:staging

# Deploy to production
npm run deploy:production
```

### CloudFront or Load Balancer Configuration

Remember to update your CloudFront distribution or load balancer to point to the new SHA path after deployment.
