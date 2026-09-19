# Deployment Setup

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

Deployment is CI's job: the Staging workflow deploys every push to `test`, and the
Production workflow every push to `main`. There are no local deploy scripts. Each run
builds, writes `out/app-config.json` for that environment, and syncs to a prefix named
after the commit sha.

### How a build becomes the live site

Each deploy uploads to `s3://<bucket>/<commit sha>/` and then promotes that build to
`s3://<bucket>/current/`, which is the prefix both CloudFront distributions serve. So a
merge to `test` or `main` is live by itself: no Terraform change, no variable to bump.

The per-sha copies stay, so putting an earlier build back is one command and takes effect
immediately (the distributions serve the default behaviour with caching disabled):

```bash
aws s3 sync s3://staging-openforge-catalog-website/<old sha> \
            s3://staging-openforge-catalog-website/current
```
