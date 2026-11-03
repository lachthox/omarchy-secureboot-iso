# Single-file ISO hosting

The selected release design hosts one ISO in S3-compatible object storage and
links it from GitHub Releases. GitHub's individual asset limit is 2 GiB; the
6.5 GB ISO cannot be attached there directly. Development artifacts remain in
Actions until the production acceptance gates pass.

Configure the following in **Settings → Secrets and variables → Actions**:

| Type | Name | Value |
| --- | --- | --- |
| Variable | `RELEASE_BUCKET` | Dedicated release bucket name |
| Variable | `RELEASE_PUBLIC_BASE_URL` | HTTPS public download base, without bucket/key suffix |
| Variable | `RELEASE_S3_ENDPOINT` | HTTPS S3 API endpoint; empty for AWS S3 |
| Variable | `RELEASE_REGION` | AWS region, or `auto` for Cloudflare R2 |
| Secret | `RELEASE_ACCESS_KEY_ID` | Bucket-scoped object upload key ID |
| Secret | `RELEASE_SECRET_ACCESS_KEY` | Corresponding secret |

Create a bucket-scoped credential with only the object permissions required for
multipart upload. Configure public access for this dedicated release bucket or
its CDN domain outside the workflow. No account credentials should be pasted
into chat or committed. Cloudflare R2, AWS S3 and compatible services can use
this interface; actual access has not yet been configured or tested.

`release.yml` verifies the successful build run, matching commit and checksum,
and production acceptance metadata. It downloads the artifact once, uploads to
a versioned SHA256-addressed key, then streams the public object back **on the
cloud runner** to verify the actual public bytes. Only after that does it publish
the GitHub release and small checksum/metadata assets. This extra release-time
transfer protects the published artifact and is outside the quick test loop.

The workflow never changes bucket-wide access policies or provisions billable
resources. Credentials are scoped to the upload step. Incomplete multipart
uploads should have a bucket lifecycle cleanup policy. Enable bucket versioning
or object lock where supported if stronger publication immutability is needed.

Sources: [GitHub release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases),
[Cloudflare R2 S3 setup](https://developers.cloudflare.com/r2/get-started/s3/),
[AWS CLI object copy](https://docs.aws.amazon.com/cli/latest/reference/s3/cp.html).
